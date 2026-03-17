"""Async event bus for decoupling components."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    """Simple async event emitter.

    Handlers are called concurrently for each event. A handler that raises
    is logged but does not block other handlers.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event: str, handler: Handler) -> None:
        """Register a handler for an event type."""
        self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Handler) -> None:
        """Remove a handler for an event type."""
        try:
            self._handlers[event].remove(handler)
        except ValueError:
            pass

    async def emit(self, event: str, payload: dict[str, Any]) -> None:
        """Emit an event to all registered handlers.

        Handlers run concurrently. Errors are logged, not raised.
        """
        handlers = self._handlers.get(event, [])
        if not handlers:
            return

        # Inject event_type so handlers can format without knowing the subscription key
        enriched = {**payload, "event_type": event}

        results = await asyncio.gather(
            *(h(enriched) for h in handlers), return_exceptions=True
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Event handler error for '%s': %s", event, result, exc_info=result
                )
