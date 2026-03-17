"""Post event bus notifications to Telegram."""

from __future__ import annotations

import logging
from typing import Any

from telegram import Bot

from cortexbot.events.bus import EventBus

logger = logging.getLogger(__name__)


class TelegramEventHandler:
    """Subscribes to event bus and posts notifications to Telegram."""

    def __init__(self, bot: Bot, event_bus: EventBus | None = None) -> None:
        self._bot = bot
        self._bus = event_bus
        if event_bus:
            self._register()

    def _register(self) -> None:
        events = [
            "task.created", "task.completed",
            "session.started", "session.completed",
            "chat.started", "chat.ended",
        ]
        for event in events:
            self._bus.subscribe(event, self._handle_event)

    async def _handle_event(self, payload: dict[str, Any]) -> None:
        chat_id = payload.get("chat_id")
        thread_id = payload.get("thread_id")
        if not chat_id:
            return

        message = self._format_event(payload)
        if message:
            try:
                kwargs = {"chat_id": chat_id, "text": message}
                if thread_id:
                    kwargs["message_thread_id"] = thread_id
                await self._bot.send_message(**kwargs)
            except Exception as e:
                logger.error("Failed to send notification: %s", e)

    async def on_task_created(self, payload: dict[str, Any]) -> None:
        """Handle task.created event directly."""
        await self._handle_event({**payload, "event_type": "task.created"})

    async def on_session_completed(self, payload: dict[str, Any]) -> None:
        """Handle session.completed event directly."""
        await self._handle_event({**payload, "event_type": "session.completed"})

    def _format_event(self, payload: dict[str, Any]) -> str | None:
        event_type = payload.get("event_type", "")
        formatters = {
            "task.created": lambda p: f"Task created: {p.get('description', '')}",
            "task.completed": lambda p: f"Task completed: {p.get('description', '')}",
            "session.started": lambda p: f"Running: {p.get('action', '')}",
            "session.completed": lambda p: f"Action `{p.get('action', '')}` {p.get('exit_reason', 'done')}",
            "chat.started": lambda p: f"Chat session started",
            "chat.ended": lambda p: f"Chat session ended ({p.get('message_count', 0)} messages)",
        }
        formatter = formatters.get(event_type)
        return formatter(payload) if formatter else None
