"""Telegram Application setup."""

from __future__ import annotations

import logging
from telegram.ext import Application, CommandHandler

from cortexbot.bot.commands import (
    cmd_ping, cmd_task, cmd_continue, cmd_cancel, cmd_status,
    cmd_budget, cmd_tasks, cmd_auto, cmd_project_add,
    cmd_project_validate, cmd_answer, init_commands,
)

logger = logging.getLogger(__name__)


def create_application(config, event_bus, task_store=None, session_manager=None) -> Application:
    """Build and configure the Telegram Application."""
    app = Application.builder().token(config.telegram.bot_token).build()

    # Wire commands module
    if task_store and session_manager:
        init_commands(config, task_store, session_manager, event_bus)

    # Register handlers
    app.add_handler(CommandHandler("ping", cmd_ping))

    # Project management
    app.add_handler(CommandHandler("project_add", cmd_project_add))
    app.add_handler(CommandHandler("project_validate", cmd_project_validate))

    # Task lifecycle
    app.add_handler(CommandHandler("task", cmd_task))
    app.add_handler(CommandHandler("continue", cmd_continue))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("auto", cmd_auto))
    app.add_handler(CommandHandler("answer", cmd_answer))

    # Monitoring
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("budget", cmd_budget))
    app.add_handler(CommandHandler("tasks", cmd_tasks))

    logger.info("Telegram application created with V2 commands")
    return app
