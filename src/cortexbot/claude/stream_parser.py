"""Defensive parser for Claude Code stream-json output.

Parses newline-delimited JSON. Unknown event types are preserved, not rejected.
Malformed lines are logged and skipped.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Events that count toward session rotation threshold
_ROTATION_COUNTED_TYPES = {"assistant", "tool_result"}

# Regex for detecting status blocks in assistant text
_STATUS_PATTERN = re.compile(r'\{"status"\s*:\s*"(complete|escalate|blocked)"')


@dataclass
class StreamEvent:
    """Parsed stream-json event."""

    type: str
    raw: dict = field(repr=False)

    # assistant fields
    text: str | None = None

    # tool_use fields
    tool_name: str | None = None
    tool_input: dict | None = None

    # tool_result fields
    content: str | None = None
    is_error: bool | None = None

    # result fields
    cost_usd: float | None = None
    duration_ms: int | None = None
    usage: dict | None = None

    # error fields
    error_message: str | None = None

    # system fields
    system_message: str | None = None

    @property
    def counts_for_rotation(self) -> bool:
        """Whether this event increments session_event_count."""
        return self.type in _ROTATION_COUNTED_TYPES


@dataclass
class StatusBlock:
    """Structured phase completion status."""

    status: str  # complete | escalate | blocked
    summary: str | None = None
    reason: str | None = None
    artifacts: list[str] = field(default_factory=list)

    @classmethod
    def from_text(cls, text: str) -> StatusBlock | None:
        """Extract status block from assistant message text.

        Scans for JSON matching {"status": "complete|escalate|blocked"}.
        Returns None if not found.
        """
        match = _STATUS_PATTERN.search(text)
        if not match:
            return None

        # Find the full JSON object starting at match position
        start = match.start()
        try:
            # Find matching closing brace
            depth = 0
            for i, ch in enumerate(text[start:], start=start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        obj = json.loads(text[start : i + 1])
                        return cls(
                            status=obj["status"],
                            summary=obj.get("summary"),
                            reason=obj.get("reason"),
                            artifacts=obj.get("artifacts", []),
                        )
        except (json.JSONDecodeError, KeyError):
            return None

        return None


def parse_stream_line(line: str) -> StreamEvent | None:
    """Parse a single stream-json line.

    Args:
        line: One line of newline-delimited JSON

    Returns:
        StreamEvent if valid, None if malformed or empty
    """
    stripped = line.strip()
    if not stripped:
        return None

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        logger.warning("Malformed stream-json line: %.100s", stripped)
        return None

    event_type = data.get("type")
    if not event_type:
        return None

    event = StreamEvent(type=event_type, raw=data)

    if event_type == "assistant":
        # Extract text from message.content array
        msg = data.get("message", {})
        content_parts = msg.get("content", [])
        texts = [p.get("text", "") for p in content_parts if p.get("type") == "text"]
        event.text = "".join(texts) if texts else None

    elif event_type == "tool_use":
        event.tool_name = data.get("tool_name")
        event.tool_input = data.get("tool_input")

    elif event_type == "tool_result":
        event.content = data.get("content")
        event.is_error = data.get("is_error", False)

    elif event_type == "result":
        event.cost_usd = data.get("cost_usd")
        event.duration_ms = data.get("duration_ms")
        event.usage = data.get("usage")

    elif event_type == "system":
        event.system_message = data.get("message")

    elif event_type == "error":
        err = data.get("error", {})
        event.error_message = err.get("message") if isinstance(err, dict) else str(err)

    return event
