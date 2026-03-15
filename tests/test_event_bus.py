"""Tests for the event bus."""

import asyncio

import pytest

from cortexbot.events.bus import EventBus


@pytest.mark.asyncio
class TestEventBus:
    """Test async event emitter."""

    async def test_subscribe_and_emit(self) -> None:
        """Handler receives emitted events."""
        bus = EventBus()
        received: list[dict] = []

        async def handler(payload: dict) -> None:
            received.append(payload)

        bus.subscribe("test.event", handler)
        await bus.emit("test.event", {"key": "value"})

        assert len(received) == 1
        assert received[0] == {"key": "value"}

    async def test_multiple_subscribers(self) -> None:
        """Multiple handlers for same event all fire."""
        bus = EventBus()
        results: list[str] = []

        async def handler_a(payload: dict) -> None:
            results.append("a")

        async def handler_b(payload: dict) -> None:
            results.append("b")

        bus.subscribe("evt", handler_a)
        bus.subscribe("evt", handler_b)
        await bus.emit("evt", {})

        assert sorted(results) == ["a", "b"]

    async def test_no_subscribers(self) -> None:
        """Emitting with no subscribers does not raise."""
        bus = EventBus()
        await bus.emit("nobody.listens", {"data": 1})

    async def test_handler_error_does_not_block_others(self) -> None:
        """One handler raising doesn't prevent other handlers from running."""
        bus = EventBus()
        results: list[str] = []

        async def bad_handler(payload: dict) -> None:
            raise RuntimeError("boom")

        async def good_handler(payload: dict) -> None:
            results.append("ok")

        bus.subscribe("evt", bad_handler)
        bus.subscribe("evt", good_handler)
        await bus.emit("evt", {})

        assert results == ["ok"]

    async def test_unsubscribe(self) -> None:
        """Unsubscribed handler no longer fires."""
        bus = EventBus()
        received: list[dict] = []

        async def handler(payload: dict) -> None:
            received.append(payload)

        bus.subscribe("evt", handler)
        bus.unsubscribe("evt", handler)
        await bus.emit("evt", {"data": 1})

        assert received == []
