"""Post event bus notifications to Telegram threads."""

from __future__ import annotations

import logging
from typing import Any

from telegram import Bot

from cortexbot.events.bus import EventBus

logger = logging.getLogger(__name__)


class TelegramEventHandler:
    """Subscribes to event bus and posts notifications to Telegram threads."""

    def __init__(self, bot: Bot, event_bus: EventBus, group_chat_id: int | None = None) -> None:
        self._bot = bot
        self._bus = event_bus
        self._group_chat_id = group_chat_id
        self._register()

    def _register(self) -> None:
        """Subscribe to all relevant events."""
        events = [
            "task.created",
            "task.completed",
            "phase.started",
            "phase.completed",
            "phase.failed",
            "phase.skipped",
            "phase.cancelled",
            "escalation.needed",
            "budget.warning",
            "budget.exhausted",
            "progress.update",
        ]
        for event in events:
            self._bus.subscribe(event, self._handle_event)

    async def _handle_event(self, payload: dict[str, Any]) -> None:
        """Format and send event notification to the relevant thread."""
        thread_id = payload.get("thread_id")
        if not thread_id:
            logger.warning("Event missing thread_id: %s", payload)
            return

        message = self._format_event(payload)
        if message:
            try:
                # Use group_chat_id if available, thread_id as message_thread_id
                chat_id = self._group_chat_id or thread_id
                kwargs: dict[str, Any] = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                }
                if self._group_chat_id and thread_id != chat_id:
                    kwargs["message_thread_id"] = thread_id
                await self._bot.send_message(**kwargs)
            except Exception as e:
                logger.error("Failed to send Telegram notification: %s", e)

    def _format_event(self, payload: dict[str, Any]) -> str | None:
        """Format an event payload into a human-readable message."""
        event_type = payload.get("event_type", "")

        formatters = {
            "task.created": lambda p: f"Task created: **{p.get('title')}**\nProject: {p.get('project')}\nAutonomy: {p.get('autonomy', 'supervised')}",
            "task.completed": lambda p: f"Task completed: **{p.get('title')}**\n{p.get('summary', '')}",
            "phase.started": lambda p: f"Phase **{p.get('phase')}** started.",
            "phase.completed": lambda p: f"Phase **{p.get('phase')}** completed.\n{p.get('summary', '')}",
            "phase.failed": lambda p: f"Phase **{p.get('phase')}** failed: {p.get('error', 'unknown')}" + ("\nWill retry." if p.get("will_retry") else "\nEscalating."),
            "phase.skipped": lambda p: f"Phase **{p.get('phase')}** skipped.",
            "phase.cancelled": lambda p: f"Phase **{p.get('phase')}** cancelled.\nReply /retry to re-run or /skip to move on.",
            "escalation.needed": lambda p: f"Escalation needed ({p.get('phase')}): {p.get('reason', 'unknown')}",
            "budget.warning": lambda p: f"Budget warning: ${p.get('remaining_usd', 0):.2f} remaining.",
            "budget.exhausted": lambda p: f"Budget exhausted (${p.get('spent_usd', 0):.2f} spent). Reply /budget <amount> to add more.",
            "progress.update": lambda p: p.get("status_text", ""),
        }

        formatter = formatters.get(event_type)
        if formatter:
            return formatter(payload)

        return None
