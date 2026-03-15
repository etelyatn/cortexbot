"""Telegram Application setup and thread management."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from cortexbot.config import BotConfig
from cortexbot.events.bus import EventBus
from cortexbot.bot.commands import (
    task_command,
    status_command,
    continue_command,
    skip_command,
    retry_command,
    cancel_command,
    tasks_command,
    budget_command,
)
from cortexbot.orchestrator.session_manager import SessionManager

logger = logging.getLogger(__name__)


async def _ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Respond to /ping with a pong."""
    await update.effective_message.reply_text("pong")


def create_application(config: BotConfig, event_bus: EventBus) -> Application:
    """Build and configure the Telegram Application.

    Args:
        config: Bot configuration
        event_bus: Event bus for component communication

    Returns:
        Configured but not-yet-started Application
    """
    app = Application.builder().token(config.telegram.bot_token).build()

    # Store shared state in bot_data
    app.bot_data["config"] = config
    app.bot_data["event_bus"] = event_bus
    app.bot_data["session_manager"] = SessionManager()

    # Register commands
    app.add_handler(CommandHandler("ping", _ping))
    app.add_handler(CommandHandler("task", task_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("continue", continue_command))
    app.add_handler(CommandHandler("skip", skip_command))
    app.add_handler(CommandHandler("retry", retry_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("tasks", tasks_command))
    app.add_handler(CommandHandler("budget", budget_command))

    logger.info("Telegram application created for group %s", config.telegram.group_id)
    return app
