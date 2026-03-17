"""Telegram Application setup."""

from __future__ import annotations

import logging
from telegram.ext import Application, CommandHandler

from cortexbot.bot.commands import (
    cmd_ping, cmd_task, cmd_continue, cmd_cancel, cmd_status,
    cmd_budget, cmd_tasks, cmd_auto, cmd_project_add,
    cmd_project_validate, cmd_editor, cmd_answer, cmd_chat,
    cmd_chat_end, cmd_chat_history, cmd_test,
)

logger = logging.getLogger(__name__)


def create_application(config, event_bus, task_store=None, session_manager=None) -> Application:
    """Build and configure the Telegram Application.

    Note: init_commands() must be called before this function to wire dependencies.
    """
    app = Application.builder().token(config.telegram.bot_token).build()

    # Register handlers
    app.add_handler(CommandHandler("ping", cmd_ping))

    # Project management
    app.add_handler(CommandHandler("project_add", cmd_project_add))
    app.add_handler(CommandHandler("project_validate", cmd_project_validate))
    app.add_handler(CommandHandler("editor", cmd_editor))

    # Task lifecycle
    app.add_handler(CommandHandler("task", cmd_task))
    app.add_handler(CommandHandler("continue", cmd_continue))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("auto", cmd_auto))
    app.add_handler(CommandHandler("answer", cmd_answer))

    # Chat
    app.add_handler(CommandHandler("chat", cmd_chat))
    app.add_handler(CommandHandler("chat_end", cmd_chat_end))
    app.add_handler(CommandHandler("chat_history", cmd_chat_history))

    # Testing
    app.add_handler(CommandHandler("test", cmd_test))

    # Monitoring
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("budget", cmd_budget))
    app.add_handler(CommandHandler("tasks", cmd_tasks))

    logger.info("Telegram application created with V2 commands")
    return app
