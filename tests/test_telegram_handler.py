"""Tests for Telegram event handler formatting."""

import pytest

from cortexbot.events.telegram_handler import TelegramEventHandler


class TestFormatEvent:
    """Test event-to-message formatting (pure logic, no Telegram API)."""

    def test_task_created(self) -> None:
        handler = TelegramEventHandler.__new__(TelegramEventHandler)
        msg = handler._format_event({
            "event_type": "task.created",
            "title": "Add feature",
            "project": "sandbox",
            "autonomy": "supervised",
        })
        assert "Add feature" in msg
        assert "sandbox" in msg

    def test_phase_completed(self) -> None:
        handler = TelegramEventHandler.__new__(TelegramEventHandler)
        msg = handler._format_event({
            "event_type": "phase.completed",
            "phase": "design",
            "summary": "Design doc written",
        })
        assert "design" in msg
        assert "completed" in msg.lower()

    def test_escalation_needed(self) -> None:
        handler = TelegramEventHandler.__new__(TelegramEventHandler)
        msg = handler._format_event({
            "event_type": "escalation.needed",
            "phase": "test",
            "reason": "Tests failed 3 times",
        })
        assert "Tests failed" in msg

    def test_unknown_event_returns_none(self) -> None:
        handler = TelegramEventHandler.__new__(TelegramEventHandler)
        msg = handler._format_event({"event_type": "unknown.event"})
        assert msg is None

    def test_budget_exhausted(self) -> None:
        handler = TelegramEventHandler.__new__(TelegramEventHandler)
        msg = handler._format_event({
            "event_type": "budget.exhausted",
            "spent_usd": 10.5,
        })
        assert "$10.50" in msg
        assert "/budget" in msg
