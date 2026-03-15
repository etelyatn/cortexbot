"""Telegram command handlers.

Each command function is registered as a CommandHandler in telegram.py.
Commands are implemented incrementally across milestones.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from telegram import Update
from telegram.ext import ContextTypes

from cortexbot.claude.cli import build_invocation, run_claude
from cortexbot.claude.stream_parser import parse_stream_line
from cortexbot.orchestrator.session_manager import SessionManager
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


async def task_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /task command — one-shot Claude Code invocation (M2)."""
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

    config = context.bot_data.get("config")
    session_mgr: SessionManager = context.bot_data.get("session_manager")

    if not config or not session_mgr:
        await update.effective_message.reply_text("Bot not fully initialized.")
        return

    # Resolve project
    project_name = args.project
    if project_name is None:
        if len(config.projects) == 1:
            project_name = next(iter(config.projects))
        else:
            projects = ", ".join(config.projects.keys())
            await update.effective_message.reply_text(
                f"Multiple projects configured. Specify --project: {projects}"
            )
            return

    if project_name not in config.projects:
        await update.effective_message.reply_text(f"Unknown project: {project_name}")
        return

    if session_mgr.is_busy:
        await update.effective_message.reply_text("Another task is running. Wait or /cancel first.")
        return

    project_path = str(config.projects[project_name].path)

    await update.effective_message.reply_text(f"Starting task: {args.title}...")

    invocation = build_invocation(
        binary=config.claude.binary,
        prompt=args.title,
        project_path=project_path,
        mcp_config=config.projects[project_name].mcp_config,
    )

    await session_mgr.acquire()
    try:
        process = await run_claude(invocation)
        session_mgr.current_pid = process.pid

        collected_text = ""
        async for raw_line in process.stdout:
            if session_mgr.cancel_requested:
                session_mgr.kill_subprocess()
                session_mgr.clear_cancel()
                await update.effective_message.reply_text("Cancelled.")
                return

            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            event = parse_stream_line(line)
            if event and event.type == "assistant" and event.text:
                collected_text += event.text

        await process.wait()

        # Send collected output to Telegram
        if collected_text:
            for chunk in chunk_message(collected_text):
                await update.effective_message.reply_text(chunk)
        else:
            await update.effective_message.reply_text("Claude completed with no text output.")
    finally:
        session_mgr.current_pid = None
        session_mgr.release()


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel — kill running subprocess."""
    session_mgr: SessionManager = context.bot_data.get("session_manager")
    if not session_mgr:
        return
    if session_mgr.is_busy:
        session_mgr.request_cancel()
        await update.effective_message.reply_text("Cancellation requested...")
    else:
        await update.effective_message.reply_text("No task currently running.")
