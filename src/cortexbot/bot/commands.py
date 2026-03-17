"""V2 Telegram command handlers."""

import asyncio
import logging
import re
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from cortexbot.orchestrator.task_manager import (
    TaskState, ReviewResult, TestResult, SessionRecord,
)
from cortexbot.orchestrator.action_tools import get_allowed_tools
from cortexbot.orchestrator.session_manager import SessionManager
from cortexbot.claude.cli import build_invocation, run_claude
from cortexbot.claude.prompts import (
    build_prompt, STATUS_BLOCK_CONTRACT, FENCE_INSTRUCTION,
    BRAINSTORM_BATCH_INSTRUCTION,
)
from cortexbot.claude.stream_parser import StatusBlock, parse_stream_line
from cortexbot.memory.store import TaskStore
from cortexbot.config import BotConfig, add_project

logger = logging.getLogger(__name__)

# Module-level references set during bot init
_config: BotConfig = None
_task_store: TaskStore = None
_session_manager: SessionManager = None
_event_bus = None


def init_commands(config, task_store, session_manager, event_bus):
    """Wire up module-level dependencies."""
    global _config, _task_store, _session_manager, _event_bus
    _config = config
    _task_store = task_store
    _session_manager = session_manager
    _event_bus = event_bus


def _resolve_project(chat_id: int):
    """Resolve project for a group chat. Returns (name, project_config) or None."""
    for name, proj in _config.projects.items():
        if proj.group_id == chat_id:
            return (name, proj)
    return None


def _get_task_for_thread(chat_id: int, thread_id: int):
    """Find active task for this Telegram thread."""
    task = _task_store.load_task(str(thread_id))
    if task and task.telegram_chat_id == chat_id:
        return task
    return None


def _slugify(text: str, max_len: int = 30) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len]


def _fence_user_message(message: str) -> str:
    """Wrap user message in UUID-fenced delimiters for prompt injection mitigation."""
    fence_id = str(_uuid.uuid4())
    return (
        f"--- USER MESSAGE [{fence_id}] ---\n"
        f"{message}\n"
        f"--- END USER MESSAGE [{fence_id}] ---"
    )


# -- /project-add ----------------------------------------------------------

async def cmd_project_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register a project: /project_add <name> <path>"""
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text("Usage: /project_add <name> <path>")
        return

    name, path_str = args[0], " ".join(args[1:])
    project_path = Path(path_str)

    errors = []
    if not project_path.exists():
        errors.append(f"Path does not exist: {path_str}")
    if not (project_path / ".mcp.json").exists():
        errors.append("Missing .mcp.json")
    if not (project_path / ".git").exists():
        errors.append("Not a git repository")

    if errors:
        await update.message.reply_text("Validation failed:\n" + "\n".join(f"- {e}" for e in errors))
        return

    chat_id = update.effective_chat.id
    config_path = Path.home() / ".cortexbot" / "config.yaml"
    add_project(config_path, name, path_str, chat_id)

    from cortexbot.config import load_config
    global _config
    _config = load_config(config_path)

    await update.message.reply_text(f"Project `{name}` registered.")


# -- /project-validate ------------------------------------------------------

async def cmd_project_validate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Full runtime health check."""
    project = _resolve_project(update.effective_chat.id)
    if not project:
        await update.message.reply_text("No project registered for this group.")
        return

    name, proj = project
    checks = []

    from cortexbot.services.unreal import check_ue_health
    health = await check_ue_health(proj.path)
    if health["connected"]:
        checks.append("OK Editor running")
    else:
        checks.append(f"FAIL Editor: {health.get('error', 'not reachable')}")

    proc = await asyncio.create_subprocess_exec(
        "git", "status", "--porcelain",
        cwd=proj.path, stdout=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    checks.append("OK Git clean" if not stdout.strip() else "FAIL Git has uncommitted changes")

    mcp_path = Path(proj.path) / proj.mcp_config
    checks.append("OK MCP config exists" if mcp_path.exists() else "FAIL MCP config not found")

    await update.message.reply_text(f"Project `{name}` health:\n" + "\n".join(checks))


# -- /task -------------------------------------------------------------------

async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/task <description> [--spec path] [--plan path]"""
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /task <description> [--spec path] [--plan path]")
        return

    project = _resolve_project(update.effective_chat.id)
    if not project:
        await update.message.reply_text("No project for this group.")
        return

    name, proj = project

    spec_path = None
    plan_path = None
    desc_parts = []
    i = 0
    while i < len(args):
        if args[i] == "--spec" and i + 1 < len(args):
            spec_path = args[i + 1]
            i += 2
        elif args[i] == "--plan" and i + 1 < len(args):
            plan_path = args[i + 1]
            i += 2
        else:
            desc_parts.append(args[i])
            i += 1

    description = " ".join(desc_parts)
    if not description:
        await update.message.reply_text("Please provide a task description.")
        return

    thread_id = update.message.message_thread_id or update.message.message_id
    task_id = str(thread_id)

    task = TaskState(
        task_id=task_id,
        project=name,
        description=description,
        spec_path=spec_path,
        plan_path=plan_path,
        token_budget=_config.defaults.token_budget,
        max_cycles=_config.defaults.max_cycles,
        telegram_chat_id=update.effective_chat.id,
        telegram_thread_id=thread_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )

    _task_store.save_task(task)
    await _event_bus.emit("task.created", {"task_id": task_id, "description": description})

    action = task.next_action
    await update.message.reply_text(
        f"Task created. Next action: `{action}`\n"
        f"Use `/continue` to start or `/auto on` for autonomous mode."
    )


# -- /continue ---------------------------------------------------------------

async def cmd_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute the next action for the task in this thread."""
    thread_id = update.message.message_thread_id or update.message.message_id
    task = _get_task_for_thread(update.effective_chat.id, thread_id)
    if not task:
        await update.message.reply_text("No active task in this thread.")
        return

    action = task.next_action
    if action in ("paused", "budget-exceeded", "escalate"):
        await update.message.reply_text(f"Task is {action}. Cannot continue.")
        return

    await _run_action(update, task, action)


async def _run_action(update: Update, task: TaskState, action: str, user_input: str = ""):
    """Spawn a Claude Code session for the given action."""
    project = _config.projects.get(task.project)
    if not project:
        await update.message.reply_text(f"Project `{task.project}` not found.")
        return

    try:
        await _session_manager.try_acquire(subprocess_type="task")
    except RuntimeError as e:
        await update.message.reply_text(str(e))
        return

    try:
        await update.message.reply_text(f"Running: `{action}`...")

        # Branch creation for implement
        if action == "implement" and not task.branch_name:
            slug = _slugify(task.description)
            branch = f"task/{task.task_id}-{slug}"
            proc = await asyncio.create_subprocess_exec(
                "git", "checkout", "-b", branch,
                cwd=project.path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            task.branch_name = branch
            _task_store.save_task(task)

        prompt = build_prompt(task, action, user_input=user_input)

        system_appendix = FENCE_INSTRUCTION + "\n\n" + STATUS_BLOCK_CONTRACT
        if action == "brainstorm":
            system_appendix += "\n\n" + BRAINSTORM_BATCH_INSTRUCTION

        session_id = str(_uuid.uuid4())
        allowed_tools = get_allowed_tools(action)

        invocation = build_invocation(
            prompt=prompt,
            session_id=session_id,
            action=action,
            mcp_config=project.mcp_config,
            system_prompt_appendix=system_appendix if action != "chat" else None,
            allowed_tools=allowed_tools,
        )
        invocation.cwd = project.path

        task.session_id = session_id
        record = SessionRecord(
            session_id=session_id,
            action=action,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        task.sessions.append(record)
        _task_store.save_task(task)

        await _event_bus.emit("session.started", {"task_id": task.task_id, "action": action})

        process = await run_claude(invocation)
        task.subprocess_pid = process.pid
        _session_manager.current_pid = process.pid
        _task_store.save_task(task)

        # Parse stream
        status_block = None
        total_tokens = 0
        last_assistant_text = ""
        async for raw_line in process.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            event = parse_stream_line(line)
            if event is None:
                continue
            if event.type == "result" and event.input_tokens > 0:
                total_tokens = event.input_tokens + event.output_tokens
            if event.type == "assistant" and event.text:
                last_assistant_text += event.text
                if len(last_assistant_text) > 10000:
                    last_assistant_text = last_assistant_text[-10000:]

        await process.wait()

        status_block = StatusBlock.from_text(last_assistant_text)

        record.ended_at = datetime.now(timezone.utc).isoformat()
        record.exit_reason = "completed" if process.returncode == 0 else "crash"
        record.tokens_used = total_tokens
        task.tokens_used += total_tokens
        task.subprocess_pid = None
        task.session_id = None

        if status_block:
            _apply_status_block(task, action, status_block)

            # Relay brainstorm questions
            if action == "brainstorm" and task.brainstorm_questions:
                questions_text = "\n".join(
                    f"{i+1}. {q}" for i, q in enumerate(task.brainstorm_questions)
                )
                await update.message.reply_text(
                    f"Before creating the spec, I have some questions:\n\n"
                    f"{questions_text}\n\n"
                    f"Reply with `/answer <your answers>` to continue."
                )
        elif process.returncode != 0:
            task.last_error = f"No status block. Exit code: {process.returncode}"
            task.status = "paused"

        task.updated_at = datetime.now(timezone.utc).isoformat()
        _task_store.save_task(task)

        await _event_bus.emit("session.completed", {
            "task_id": task.task_id, "action": action,
            "exit_reason": record.exit_reason,
        })

        next_act = task.next_action
        await update.message.reply_text(
            f"Action `{action}` complete. Next: `{next_act}`\n"
            f"Tokens used: {task.tokens_used:,} / {task.token_budget:,}"
        )

    finally:
        _session_manager.release()

    # Auto mode chaining
    while task.auto_mode:
        next_act = task.next_action
        if next_act in ("paused", "budget-exceeded", "escalate", "brainstorm"):
            break
        await _run_action(update, task, next_act)


def _apply_status_block(task: TaskState, action: str, block: StatusBlock):
    """Apply status block outcome to task state."""
    if block.status == "escalate":
        task.status = "paused"
        task.last_error = block.reason
        return

    if block.status == "blocked" and action == "brainstorm":
        task.brainstorm_questions = block.questions
        task.status = "paused"
        return

    if block.status == "complete":
        if action in ("brainstorm", "brainstorm-spec") and block.artifacts:
            task.spec_path = block.artifacts[0]
        elif action == "plan" and block.artifacts:
            task.plan_path = block.artifacts[0]
        elif action in ("implement", "fix-review", "fix-tests"):
            task.implementation_complete = True
            if action == "fix-review":
                task.review_result = None
            elif action == "fix-tests":
                task.test_result = None
        elif action == "review":
            task.review_result = ReviewResult(
                passed=block.review_passed if block.review_passed is not None else True,
                feedback_summary=block.feedback or block.summary or "",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            if not task.review_result.passed:
                task.review_cycle += 1
                task.implementation_complete = False
        elif action == "finish":
            task.status = "completed"


# -- /auto -------------------------------------------------------------------

async def cmd_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/auto on|off"""
    thread_id = update.message.message_thread_id or update.message.message_id
    task = _get_task_for_thread(update.effective_chat.id, thread_id)
    if not task:
        await update.message.reply_text("No active task in this thread.")
        return

    args = context.args or []
    if not args or args[0] not in ("on", "off"):
        await update.message.reply_text("Usage: /auto on|off")
        return

    task.auto_mode = args[0] == "on"
    _task_store.save_task(task)
    await update.message.reply_text(f"Auto mode: {'ON' if task.auto_mode else 'OFF'}")


# -- /cancel -----------------------------------------------------------------

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kill running subprocess, pause task."""
    thread_id = update.message.message_thread_id or update.message.message_id
    task = _get_task_for_thread(update.effective_chat.id, thread_id)
    if not task:
        await update.message.reply_text("No active task in this thread.")
        return

    if task.subprocess_pid:
        _session_manager.kill_subprocess()
        task.subprocess_pid = None
        task.status = "paused"
        _task_store.save_task(task)
        await update.message.reply_text("Task cancelled. Use `/continue` to resume.")
    else:
        task.status = "cancelled"
        _task_store.save_task(task)
        await update.message.reply_text("Task cancelled.")


# -- /status -----------------------------------------------------------------

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show task status."""
    thread_id = update.message.message_thread_id or update.message.message_id
    task = _get_task_for_thread(update.effective_chat.id, thread_id)
    if not task:
        await update.message.reply_text("No active task in this thread.")
        return

    def _fmt(result):
        if result is None:
            return "---"
        label = getattr(result, 'summary', None) or getattr(result, 'feedback_summary', '')
        return f"{'PASS' if result.passed else 'FAIL'} {label}"

    lines = [
        f"Task: {task.description}",
        f"Status: {task.status}",
        f"Next action: {task.next_action}",
        f"Tokens: {task.tokens_used:,} / {task.token_budget:,}",
        "",
        "Artifacts:",
        f"  Spec: {task.spec_path or '---'}",
        f"  Plan: {task.plan_path or '---'}",
        f"  Branch: {task.branch_name or '---'}",
        f"  Implemented: {'Yes' if task.implementation_complete else 'No'}",
        f"  Review: {_fmt(task.review_result)}",
        f"  Tests: {_fmt(task.test_result)}",
        "",
        f"Auto mode: {'ON' if task.auto_mode else 'OFF'}",
        f"Sessions: {len(task.sessions)}",
    ]
    await update.message.reply_text("\n".join(lines))


# -- /budget -----------------------------------------------------------------

async def cmd_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/budget [amount]"""
    thread_id = update.message.message_thread_id or update.message.message_id
    task = _get_task_for_thread(update.effective_chat.id, thread_id)
    if not task:
        await update.message.reply_text("No active task in this thread.")
        return

    args = context.args or []
    if args:
        try:
            task.token_budget = int(args[0])
            _task_store.save_task(task)
        except ValueError:
            await update.message.reply_text("Invalid amount.")
            return

    await update.message.reply_text(
        f"Budget: {task.tokens_used:,} / {task.token_budget:,} tokens"
    )


# -- /tasks ------------------------------------------------------------------

async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all active tasks."""
    all_tasks = _task_store.list_tasks()
    active = [t for t in all_tasks if t.status in ("active", "paused")]

    if not active:
        await update.message.reply_text("No active tasks.")
        return

    lines = []
    for t in active:
        lines.append(f"[{t.task_id}] {t.description} -- {t.next_action} ({t.status})")
    await update.message.reply_text("\n".join(lines))


# -- /answer -----------------------------------------------------------------

async def cmd_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/answer <text> -- provide answers to brainstorm questions."""
    thread_id = update.message.message_thread_id or update.message.message_id
    task = _get_task_for_thread(update.effective_chat.id, thread_id)
    if not task:
        await update.message.reply_text("No active task in this thread.")
        return

    if not task.brainstorm_questions:
        await update.message.reply_text("No pending brainstorm questions.")
        return

    user_answers = " ".join(context.args or [])
    if not user_answers:
        await update.message.reply_text("Usage: /answer <your answers>")
        return

    fenced_answers = _fence_user_message(user_answers)

    task.brainstorm_questions = []
    task.status = "active"
    _task_store.save_task(task)

    await _run_action(update, task, "brainstorm-spec", user_input=fenced_answers)


# -- /ping -------------------------------------------------------------------

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")


# ── /chat ─────────────────────────────────────────────────

async def cmd_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/chat <message> — start or continue a freeform chat session."""
    args = context.args or []
    if not args:
        await update.message.reply_text("Usage: /chat <message>")
        return

    project = _resolve_project(update.effective_chat.id)
    if not project:
        await update.message.reply_text("No project for this group.")
        return

    name, proj = project
    message = " ".join(args)
    fenced_message = _fence_user_message(message)

    thread_id = update.message.message_thread_id or update.message.message_id

    # Find or create chat session
    from cortexbot.chat.store import ChatSessionStore
    chat_store = ChatSessionStore(base_dir=Path.home() / ".cortexbot")

    existing = chat_store.find_by_thread(update.effective_chat.id, thread_id)
    is_resume = existing is not None

    if existing:
        session = existing
    else:
        from cortexbot.chat.session import ChatSession
        session = ChatSession(
            session_id=str(_uuid.uuid4()),
            project=name,
            telegram_chat_id=update.effective_chat.id,
            telegram_thread_id=thread_id,
        )
        chat_store.save(session)
        await _event_bus.emit("chat.started", {"session_id": session.session_id, "project": name})

    # Acquire session mutex
    try:
        await _session_manager.try_acquire(subprocess_type="chat")
    except RuntimeError as e:
        await update.message.reply_text(str(e))
        return

    try:
        invocation = build_invocation(
            prompt=fenced_message,
            session_id=session.session_id,
            action="chat",
            mcp_config=proj.mcp_config,
            resume=is_resume,
        )
        invocation.cwd = proj.path

        process = await run_claude(invocation)
        session.subprocess_pid = process.pid
        _session_manager.current_pid = process.pid
        chat_store.save(session)

        # Collect response
        response_text = ""
        total_tokens = 0
        async for raw_line in process.stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            event = parse_stream_line(line)
            if event is None:
                continue
            if event.type == "assistant" and event.text:
                response_text += event.text
            if event.type == "result" and event.input_tokens > 0:
                total_tokens = event.input_tokens + event.output_tokens

        await process.wait()

        session.message_count += 1
        session.tokens_used += total_tokens
        session.subprocess_pid = None
        from datetime import datetime, timezone
        session.last_activity = datetime.now(timezone.utc).isoformat()
        chat_store.save(session)

        # Send response (truncate if too long for Telegram)
        if response_text:
            if len(response_text) > 4000:
                response_text = response_text[:4000] + "\n...(truncated)"
            await update.message.reply_text(response_text)
        else:
            await update.message.reply_text("(no response)")

    finally:
        _session_manager.release()


# ── /chat_end ─────────────────────────────────────────────

async def cmd_chat_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End the current chat session."""
    thread_id = update.message.message_thread_id or update.message.message_id

    from cortexbot.chat.store import ChatSessionStore
    chat_store = ChatSessionStore(base_dir=Path.home() / ".cortexbot")
    session = chat_store.find_by_thread(update.effective_chat.id, thread_id)

    if not session:
        await update.message.reply_text("No active chat session in this thread.")
        return

    await _event_bus.emit("chat.ended", {
        "session_id": session.session_id,
        "message_count": session.message_count,
    })
    chat_store.delete(session.session_id)
    await update.message.reply_text(
        f"Chat ended. {session.message_count} messages, {session.tokens_used:,} tokens."
    )


# ── /chat_history ─────────────────────────────────────────

async def cmd_chat_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List active chat sessions."""
    from cortexbot.chat.store import ChatSessionStore
    chat_store = ChatSessionStore(base_dir=Path.home() / ".cortexbot")
    sessions = chat_store.list_sessions()

    if not sessions:
        await update.message.reply_text("No active chat sessions.")
        return

    lines = []
    for s in sessions:
        lines.append(f"• [{s.session_id[:8]}] {s.project} — {s.message_count} msgs, {s.tokens_used:,} tokens")
    await update.message.reply_text("\n".join(lines))
