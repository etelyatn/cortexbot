"""Telegram command handlers.

Each command function is registered as a CommandHandler in telegram.py.
Commands are implemented incrementally across milestones.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Coroutine

from telegram import Update
from telegram.ext import ContextTypes

from cortexbot.claude.cli import build_invocation, run_claude
from cortexbot.claude.prompt_builder import load_template, build_prompt
from cortexbot.claude.stream_parser import parse_stream_line, StatusBlock
from cortexbot.config import BotConfig
from cortexbot.events.bus import EventBus
from cortexbot.health.preflight import check_editor_alive, check_git_branch
from cortexbot.log import InvocationLogger
from cortexbot.memory.artifacts import extract_artifacts_from_status
from cortexbot.memory.store import TaskStore
from cortexbot.orchestrator.autonomy import (
    AutonomyDecision,
    decide_on_error,
    decide_on_phase_complete,
    should_auto_advance,
)
from cortexbot.orchestrator.phase_gates import validate_gate
from cortexbot.orchestrator.phase_tools import get_allowed_tools
from cortexbot.orchestrator.session_manager import SessionManager
from cortexbot.orchestrator.task_manager import TaskState, PhaseRecord, next_phase, PHASES
from cortexbot.bot.media import chunk_message

logger = logging.getLogger(__name__)


@dataclass
class TaskArgs:
    """Parsed /task command arguments."""

    title: str
    project: str | None = None
    autonomy: str | None = None


def parse_task_args(text: str) -> TaskArgs:
    """Parse /task arguments: title [--project X] [--autonomy Y].

    Args:
        text: Raw argument text after /task

    Returns:
        Parsed TaskArgs

    Raises:
        ValueError: If title is empty
    """
    parts = text.strip().split()
    if not parts:
        raise ValueError("Task title is required")

    title_parts: list[str] = []
    project: str | None = None
    autonomy: str | None = None

    i = 0
    while i < len(parts):
        if parts[i] == "--project" and i + 1 < len(parts):
            project = parts[i + 1]
            i += 2
        elif parts[i] == "--autonomy" and i + 1 < len(parts):
            autonomy = parts[i + 1]
            i += 2
        elif parts[i].startswith("--"):
            i += 1  # skip unknown flags
        else:
            title_parts.append(parts[i])
            i += 1

    title = " ".join(title_parts).strip()
    if not title:
        raise ValueError("Task title is required")

    return TaskArgs(title=title, project=project, autonomy=autonomy)


async def _safe_run_task(
    coro: Coroutine[Any, Any, None],
    event_bus: EventBus,
    thread_id: int,
) -> None:
    """Wrapper for fire-and-forget tasks — catches and reports exceptions."""
    try:
        await coro
    except Exception:
        logger.exception("Task loop crashed for thread %d", thread_id)
        await event_bus.emit("escalation.needed", {
            "event_type": "escalation.needed",
            "thread_id": thread_id,
            "phase": "unknown",
            "reason": "Internal error — task loop crashed. Check bot logs.",
        })


async def _create_task_branch(project_path: str, branch: str, default_branch: str) -> bool:
    """Create and checkout a new task branch.

    Uses asyncio subprocess to avoid blocking the event loop.
    Returns True on success, False on failure.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "checkout", default_branch,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=project_path,
        )
        await asyncio.wait_for(proc.wait(), timeout=10)

        proc = await asyncio.create_subprocess_exec(
            "git", "checkout", "-b", branch,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=project_path,
        )
        await asyncio.wait_for(proc.wait(), timeout=10)
        return proc.returncode == 0
    except (OSError, asyncio.TimeoutError) as e:
        logger.error("Failed to create branch %s: %s", branch, e)
        return False


async def _run_phase_once(
    task: TaskState,
    store: TaskStore,
    session_mgr: SessionManager,
    event_bus: EventBus,
    config: BotConfig,
    prompts_dir: Path,
    inv_logger: InvocationLogger,
) -> "StatusBlock | None":
    """Execute a single Claude Code invocation for the current phase.

    Acquires and releases the mutex. Returns the status block from Claude,
    or None if cancelled.
    """
    project_config = config.projects[task.project]
    project_path = str(project_config.path)

    # Build prompt
    template_file = prompts_dir / f"{task.current_phase}_phase.md"
    if template_file.exists():
        template = load_template(template_file)
    else:
        template = f"Execute the {task.current_phase} phase for task: {{{{title}}}}"

    autonomy_file = prompts_dir / f"{task.autonomy}.md"
    autonomy_rules = load_template(autonomy_file) if autonomy_file.exists() else ""

    prompt_vars = {
        "project_name": task.project,
        "branch": task.branch,
        "title": task.title,
        "autonomy_rules": autonomy_rules,
        "phase_history": "\n".join(
            f"- {r.phase}: {r.summary}" for r in task.phase_history
        ),
        "error_context": task.last_error or "",
    }

    for artifact in task.artifacts:
        if artifact.artifact_type == "design_doc":
            prompt_vars["design_doc_path"] = artifact.path
        elif artifact.artifact_type == "impl_guide":
            prompt_vars["impl_guide_path"] = artifact.path

    system_prompt = build_prompt(template, **prompt_vars)

    # Session decision
    if task.retry_count == 1 and task.session_id:
        resume_id = task.session_id
        session_id = None
    else:
        resume_id = None
        session_id = str(uuid.uuid4())
        task.session_id = session_id

    invocation = build_invocation(
        binary=config.claude.binary,
        prompt=f"Execute the {task.current_phase} phase for: {task.title}",
        project_path=project_path,
        session_id=session_id,
        resume_session_id=resume_id,
        system_prompt=system_prompt,
        max_budget_usd=task.calculate_phase_budget(),
        allowed_tools=get_allowed_tools(task.current_phase),
        mcp_config=project_config.mcp_config,
    )

    # Create invocation log
    log_path = inv_logger.create_log(task.thread_id, task.current_phase)

    # Preflight checks
    editor_check = check_editor_alive(project_config.path)
    if not editor_check.passed:
        return StatusBlock(status="escalate", reason=f"Preflight failed: {editor_check.reason}")

    branch_check = check_git_branch(project_config.path, task.branch)
    if not branch_check.passed:
        return StatusBlock(status="escalate", reason=f"Preflight failed: {branch_check.reason}")

    # Phase timeout from config
    timeout_secs = config.defaults.timeouts.get(
        task.current_phase, config.defaults.timeouts.get("default", 900)
    )

    # Clear any stale cancel flag from a previous cancellation
    session_mgr.clear_cancel()

    await session_mgr.acquire()
    try:
        task.current_phase_status = "in_progress"
        store.save_task(task)

        await event_bus.emit("phase.started", {
            "event_type": "phase.started",
            "thread_id": task.thread_id,
            "phase": task.current_phase,
        })

        process = await run_claude(invocation)
        task.subprocess_pid = process.pid
        store.save_task(task)
        session_mgr.current_pid = process.pid

        last_assistant_text = ""
        event_count = 0
        cost_usd = 0.0

        async def _read_stream() -> None:
            nonlocal last_assistant_text, event_count, cost_usd
            async for raw_line in process.stdout:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                inv_logger.append_line(log_path, line)
                event = parse_stream_line(line)
                if event is None:
                    continue
                if event.counts_for_rotation:
                    event_count += 1
                if event.type == "assistant" and event.text:
                    last_assistant_text = event.text
                if event.type == "result" and event.cost_usd is not None:
                    cost_usd = event.cost_usd
                if session_mgr.cancel_requested:
                    session_mgr.kill_subprocess()
                    break

        try:
            await asyncio.wait_for(_read_stream(), timeout=timeout_secs)
        except asyncio.TimeoutError:
            session_mgr.kill_subprocess()
            task.subprocess_pid = None
            session_mgr.current_pid = None
            task.current_phase_status = "interrupted"
            store.save_task(task)
            await event_bus.emit("escalation.needed", {
                "event_type": "escalation.needed",
                "thread_id": task.thread_id,
                "phase": task.current_phase,
                "reason": f"Phase timed out after {timeout_secs}s",
            })
            return None

        return_code = await process.wait()

        task.subprocess_pid = None
        task.session_event_count = event_count
        session_mgr.current_pid = None

        if cost_usd > 0:
            task.deduct_cost(cost_usd)

        # Cancelled
        if session_mgr.cancel_requested:
            task.current_phase_status = "interrupted"
            session_mgr.clear_cancel()
            store.save_task(task)
            await event_bus.emit("phase.cancelled", {
                "event_type": "phase.cancelled",
                "thread_id": task.thread_id,
                "phase": task.current_phase,
            })
            return None

        # Extract status block
        status_block = StatusBlock.from_text(last_assistant_text)
        if status_block is None:
            if return_code == 0:
                status_block = StatusBlock(
                    status="complete",
                    summary=last_assistant_text[:200] if last_assistant_text else "Phase completed",
                )
            else:
                status_block = StatusBlock(
                    status="escalate",
                    reason=f"No status block produced. Exit code: {return_code}",
                )

        store.save_task(task)
        return status_block

    finally:
        session_mgr.current_pid = None
        session_mgr.release()


async def _run_task_loop(
    task: TaskState,
    store: TaskStore,
    session_mgr: SessionManager,
    event_bus: EventBus,
    config: BotConfig,
    prompts_dir: Path,
) -> None:
    """Orchestration loop: run phases, handle retries and advances."""
    base_dir = Path.home() / ".cortexbot"
    inv_logger = InvocationLogger(base_dir)
    previous_error: str | None = None

    while True:
        status_block = await _run_phase_once(
            task, store, session_mgr, event_bus, config, prompts_dir, inv_logger
        )

        if status_block is None:
            return

        # Phase rollback: Test failure can roll back to Implement
        if (
            status_block.status in ("escalate", "blocked")
            and task.current_phase == "test"
            and task.autonomy == "autonomous"
            and task.retry_count >= 2
        ):
            task.phase_history.append(PhaseRecord(
                phase="test",
                status="rolled_back",
                summary=status_block.reason,
            ))
            task.current_phase = "implement"
            task.current_phase_status = "pending"
            task.retry_count = 0
            task.last_error = f"Test phase rolled back: {status_block.reason}"
            previous_error = None
            store.save_task(task)
            continue

        # Error / escalate / blocked
        if status_block.status in ("escalate", "blocked"):
            current_error = status_block.reason or ""
            same_error = (previous_error is not None and current_error == previous_error)
            previous_error = current_error

            task.last_error = current_error
            task.current_phase_status = "interrupted"
            store.save_task(task)

            decision = decide_on_error(task.autonomy, task.retry_count, same_error)
            will_retry = decision == AutonomyDecision.RETRY

            await event_bus.emit("phase.failed", {
                "event_type": "phase.failed",
                "thread_id": task.thread_id,
                "phase": task.current_phase,
                "error": current_error,
                "will_retry": will_retry,
            })

            if will_retry:
                task.retry_count += 1
                store.save_task(task)
                continue
            else:
                await event_bus.emit("escalation.needed", {
                    "event_type": "escalation.needed",
                    "thread_id": task.thread_id,
                    "phase": task.current_phase,
                    "reason": current_error,
                })
                return

        # Complete — validate gate
        project_config = config.projects[task.project]
        artifacts = status_block.artifacts or []
        gate = validate_gate(
            task.current_phase,
            project_config.path,
            artifacts=artifacts,
            branch=task.branch,
            default_branch=project_config.default_branch,
            status_complete=True,
        )

        if gate.passed:
            previous_error = None

            classified = extract_artifacts_from_status(artifacts, task.current_phase)
            for a in classified:
                task.add_artifact(a["type"], a["path"], a["phase"])

            task.advance_phase(summary=status_block.summary, artifacts=artifacts)
            store.save_task(task)

            await event_bus.emit("phase.completed", {
                "event_type": "phase.completed",
                "thread_id": task.thread_id,
                "phase": task.phase_history[-1].phase,
                "summary": status_block.summary,
                "artifacts": artifacts,
            })

            if task.current_phase_status == "done":
                await event_bus.emit("task.completed", {
                    "event_type": "task.completed",
                    "thread_id": task.thread_id,
                    "title": task.title,
                    "summary": status_block.summary,
                })
                return

            decision = decide_on_phase_complete(task.autonomy, gate_passed=True)
            if decision == AutonomyDecision.ADVANCE:
                continue
            else:
                return

        else:
            task.last_error = gate.reason
            task.current_phase_status = "interrupted"
            store.save_task(task)

            decision = decide_on_phase_complete(task.autonomy, gate_passed=False)
            if decision == AutonomyDecision.RETRY:
                task.retry_count += 1
                store.save_task(task)
                continue
            else:
                await event_bus.emit("phase.failed", {
                    "event_type": "phase.failed",
                    "thread_id": task.thread_id,
                    "phase": task.current_phase,
                    "error": gate.reason,
                    "will_retry": False,
                })
                return


async def task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /task command — create a new task and start Design phase."""
    if not update.effective_message or not update.effective_message.text:
        return

    raw_text = update.effective_message.text
    arg_text = raw_text.split(maxsplit=1)[1] if " " in raw_text else ""

    try:
        args = parse_task_args(arg_text)
    except ValueError as e:
        await update.effective_message.reply_text(
            f"Usage: /task <title> [--project X] [--autonomy Y]\nError: {e}"
        )
        return

    config: BotConfig = context.bot_data["config"]
    store: TaskStore = context.bot_data["store"]
    session_mgr: SessionManager = context.bot_data["session_manager"]
    event_bus: EventBus = context.bot_data["event_bus"]

    # Resolve project
    project_name = args.project
    if project_name is None:
        if len(config.projects) == 1:
            project_name = next(iter(config.projects))
        else:
            projects = ", ".join(config.projects.keys())
            await update.effective_message.reply_text(
                f"Multiple projects configured. Specify one with --project: {projects}"
            )
            return

    if project_name not in config.projects:
        await update.effective_message.reply_text(f"Unknown project: {project_name}")
        return

    # Get thread ID
    thread_id = update.effective_message.message_thread_id or update.effective_chat.id

    # Check for existing task
    existing = store.load_task(thread_id)
    if existing and existing.current_phase_status != "done":
        await update.effective_message.reply_text(
            f"This thread already has an active task: {existing.title}"
        )
        return

    # Create task
    autonomy = args.autonomy or config.defaults.autonomy
    task = TaskState.create(
        thread_id=thread_id,
        title=args.title,
        project=project_name,
        budget_usd=config.defaults.budget_usd,
        autonomy=autonomy,
    )
    store.save_task(task)

    # Create git branch
    project_path = str(config.projects[project_name].path)
    default_branch = config.projects[project_name].default_branch
    branch_created = await _create_task_branch(project_path, task.branch, default_branch)
    if not branch_created:
        await update.effective_message.reply_text(
            f"Warning: Could not create branch `{task.branch}`. Check git state."
        )

    await event_bus.emit("task.created", {
        "event_type": "task.created",
        "thread_id": thread_id,
        "title": task.title,
        "project": project_name,
        "autonomy": autonomy,
    })

    await update.effective_message.reply_text(
        f"Task created: **{task.title}**\n"
        f"Project: {project_name}\n"
        f"Branch: `{task.branch}`\n"
        f"Autonomy: {autonomy}\n"
        f"Starting Design phase...",
        parse_mode="Markdown",
    )

    # Start first phase (fire-and-forget so Telegram handler stays responsive)
    prompts_dir = Path(__file__).parent.parent.parent.parent / "prompts"
    asyncio.create_task(_safe_run_task(
        _run_task_loop(task, store, session_mgr, event_bus, config, prompts_dir),
        event_bus, thread_id,
    ))


def parse_skip_args(text: str) -> str | None:
    """Parse /skip arguments.

    Args:
        text: Raw argument text after /skip

    Returns:
        Target phase name, or None to skip just the current phase

    Raises:
        ValueError: If specified phase doesn't exist
    """
    stripped = text.strip()
    if not stripped:
        return None

    if stripped not in PHASES:
        raise ValueError(f"Unknown phase: '{stripped}'. Valid phases: {', '.join(PHASES)}")

    return stripped


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status — show current task state."""
    store = context.bot_data.get("store")
    if not store or not update.effective_message:
        return

    thread_id = update.effective_message.message_thread_id or update.effective_chat.id
    task = store.load_task(thread_id)

    if not task:
        await update.effective_message.reply_text("No task in this thread.")
        return

    lines = [
        f"**Task:** {task.title}",
        f"**Project:** {task.project}",
        f"**Branch:** `{task.branch}`",
        f"**Phase:** {task.current_phase} ({task.current_phase_status})",
        f"**Autonomy:** {task.autonomy}",
        f"**Budget:** ${task.budget_usd:.2f} remaining",
        f"**Retries:** {task.retry_count}",
    ]
    if task.artifacts:
        lines.append("**Artifacts:**")
        for a in task.artifacts:
            lines.append(f"  - [{a.artifact_type}] {a.path}")

    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")


async def continue_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /continue — approve phase result and advance to next phase."""
    if not update.effective_message:
        return

    store: TaskStore = context.bot_data["store"]
    session_mgr: SessionManager = context.bot_data["session_manager"]
    event_bus: EventBus = context.bot_data["event_bus"]
    config: BotConfig = context.bot_data["config"]

    thread_id = update.effective_message.message_thread_id or update.effective_chat.id
    task = store.load_task(thread_id)

    if not task:
        await update.effective_message.reply_text("No task in this thread.")
        return

    if task.current_phase_status == "in_progress":
        await update.effective_message.reply_text("Phase still running. Wait for it to complete.")
        return

    if task.current_phase_status == "done":
        await update.effective_message.reply_text("Task already completed.")
        return

    if task.current_phase_status in ("completed", "pending"):
        await update.effective_message.reply_text(f"Starting {task.current_phase} phase...")
        prompts_dir = Path(__file__).parent.parent.parent.parent / "prompts"
        asyncio.create_task(_safe_run_task(
            _run_task_loop(task, store, session_mgr, event_bus, config, prompts_dir),
            event_bus, task.thread_id,
        ))
    elif task.current_phase_status == "interrupted":
        await update.effective_message.reply_text(
            f"Phase {task.current_phase} was interrupted. Use /retry to re-run or /skip to move on."
        )


async def skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /skip [phase] — skip current or advance to target phase."""
    if not update.effective_message or not update.effective_message.text:
        return

    store: TaskStore = context.bot_data["store"]
    thread_id = update.effective_message.message_thread_id or update.effective_chat.id
    task = store.load_task(thread_id)

    if not task:
        await update.effective_message.reply_text("No task in this thread.")
        return

    if task.current_phase_status == "in_progress":
        await update.effective_message.reply_text("Phase in progress. Use /cancel first.")
        return

    if task.current_phase_status == "done":
        await update.effective_message.reply_text("Task already completed.")
        return

    raw_text = update.effective_message.text
    arg_text = raw_text.split(maxsplit=1)[1] if " " in raw_text else ""

    try:
        target = parse_skip_args(arg_text)
    except ValueError as e:
        await update.effective_message.reply_text(str(e))
        return

    # Skip current phase (or multiple phases to reach target)
    skipped_phases = []
    if target:
        while task.current_phase != target and task.current_phase_status != "done":
            skipped_phases.append(task.current_phase)
            task.phase_history.append(PhaseRecord(
                phase=task.current_phase, status="skipped",
            ))
            nxt = next_phase(task.current_phase)
            if nxt is None:
                break
            task.current_phase = nxt
            task.current_phase_status = "pending"
            task.retry_count = 0
    else:
        skipped_phases.append(task.current_phase)
        task.phase_history.append(PhaseRecord(
            phase=task.current_phase, status="skipped",
        ))
        nxt = next_phase(task.current_phase)
        if nxt is None:
            task.current_phase_status = "done"
        else:
            task.current_phase = nxt
            task.current_phase_status = "pending"
            task.retry_count = 0

    store.save_task(task)
    skipped_str = ", ".join(skipped_phases)
    await update.effective_message.reply_text(
        f"Skipped: {skipped_str}. Now at: {task.current_phase} ({task.current_phase_status})"
    )


async def retry_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /retry — re-run current phase."""
    if not update.effective_message:
        return

    store: TaskStore = context.bot_data["store"]
    session_mgr: SessionManager = context.bot_data["session_manager"]
    event_bus: EventBus = context.bot_data["event_bus"]
    config: BotConfig = context.bot_data["config"]

    thread_id = update.effective_message.message_thread_id or update.effective_chat.id
    task = store.load_task(thread_id)

    if not task:
        await update.effective_message.reply_text("No task in this thread.")
        return

    if task.current_phase_status == "in_progress":
        await update.effective_message.reply_text("Phase in progress. Use /cancel first.")
        return

    task.retry_count += 1
    task.current_phase_status = "pending"
    store.save_task(task)

    await update.effective_message.reply_text(
        f"Retrying {task.current_phase} phase (attempt {task.retry_count + 1})..."
    )
    prompts_dir = Path(__file__).parent.parent.parent.parent / "prompts"
    asyncio.create_task(_safe_run_task(
        _run_task_loop(task, store, session_mgr, event_bus, config, prompts_dir),
        event_bus, task.thread_id,
    ))


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel — kill running subprocess."""
    session_mgr = context.bot_data.get("session_manager")
    if session_mgr:
        session_mgr.request_cancel()
        killed = session_mgr.kill_subprocess()
        if killed:
            await update.effective_message.reply_text(
                "Cancelled. Reply /retry to re-run this phase or /skip to move on."
            )
        else:
            await update.effective_message.reply_text("No phase currently running.")
    else:
        await update.effective_message.reply_text("Session manager not initialized.")


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tasks — list all active tasks."""
    store = context.bot_data.get("store")
    if not store:
        await update.effective_message.reply_text("Store not initialized.")
        return

    all_tasks = store.list_tasks()
    active = [t for t in all_tasks if t.current_phase_status != "done"]

    if not active:
        await update.effective_message.reply_text("No active tasks.")
        return

    lines = ["**Active Tasks:**"]
    for t in sorted(active, key=lambda x: x.updated_at, reverse=True):
        lines.append(
            f"- [{t.title}] {t.project} — {t.current_phase} ({t.current_phase_status})"
        )

    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")


async def budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /budget [amount] — show or add budget."""
    if not update.effective_message:
        return

    store: TaskStore = context.bot_data["store"]
    thread_id = update.effective_message.message_thread_id or update.effective_chat.id
    task = store.load_task(thread_id)

    if not task:
        await update.effective_message.reply_text("No task in this thread.")
        return

    raw_text = update.effective_message.text or ""
    arg_text = raw_text.split(maxsplit=1)[1].strip() if " " in raw_text else ""

    if not arg_text:
        await update.effective_message.reply_text(
            f"Budget: ${task.budget_usd:.2f} remaining\n"
            f"Phase: {task.current_phase} (budget cap: ${task.calculate_phase_budget():.2f})"
        )
        return

    try:
        amount = float(arg_text)
    except ValueError:
        await update.effective_message.reply_text("Usage: /budget [amount]")
        return

    task.add_budget(amount)
    store.save_task(task)
    await update.effective_message.reply_text(
        f"Added ${amount:.2f}. New balance: ${task.budget_usd:.2f}"
    )
