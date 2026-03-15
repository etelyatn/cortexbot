"""Tests for Claude Code stream-json parser."""

import pytest

from cortexbot.claude.stream_parser import StreamEvent, parse_stream_line, StatusBlock


class TestParseStreamLine:
    """Test parsing individual stream-json lines."""

    def test_assistant_event(self) -> None:
        """Parse assistant message event."""
        line = '{"type":"assistant","message":{"content":[{"type":"text","text":"Hello world"}]}}'
        event = parse_stream_line(line)
        assert event is not None
        assert event.type == "assistant"
        assert event.text == "Hello world"

    def test_tool_use_event(self) -> None:
        """Parse tool_use event."""
        line = '{"type":"tool_use","tool_name":"Read","tool_input":{"file_path":"/tmp/test.py"}}'
        event = parse_stream_line(line)
        assert event is not None
        assert event.type == "tool_use"
        assert event.tool_name == "Read"

    def test_tool_result_event(self) -> None:
        """Parse tool_result event."""
        line = '{"type":"tool_result","content":"file contents here","is_error":false}'
        event = parse_stream_line(line)
        assert event is not None
        assert event.type == "tool_result"
        assert event.is_error is False

    def test_result_event_with_cost(self) -> None:
        """Parse result event with cost info."""
        line = '{"type":"result","cost_usd":0.42,"duration_ms":5000,"usage":{"input_tokens":1000,"output_tokens":500}}'
        event = parse_stream_line(line)
        assert event is not None
        assert event.type == "result"
        assert event.cost_usd == 0.42
        assert event.duration_ms == 5000

    def test_system_event(self) -> None:
        """Parse system event."""
        line = '{"type":"system","message":"Session started"}'
        event = parse_stream_line(line)
        assert event is not None
        assert event.type == "system"

    def test_error_event(self) -> None:
        """Parse error event."""
        line = '{"type":"error","error":{"message":"Rate limited"}}'
        event = parse_stream_line(line)
        assert event is not None
        assert event.type == "error"
        assert event.error_message == "Rate limited"

    def test_unknown_event_type_returns_generic(self) -> None:
        """Unknown event types are parsed but not rejected."""
        line = '{"type":"future_event","data":"something"}'
        event = parse_stream_line(line)
        assert event is not None
        assert event.type == "future_event"

    def test_malformed_json_returns_none(self) -> None:
        """Malformed JSON lines return None (not raise)."""
        event = parse_stream_line("not json at all")
        assert event is None

    def test_empty_line_returns_none(self) -> None:
        """Empty lines return None."""
        assert parse_stream_line("") is None
        assert parse_stream_line("   ") is None

    def test_missing_type_returns_none(self) -> None:
        """JSON without 'type' field returns None."""
        event = parse_stream_line('{"data": "no type here"}')
        assert event is None

    def test_counts_assistant_events(self) -> None:
        """assistant events are countable (for session rotation)."""
        line = '{"type":"assistant","message":{"content":[{"type":"text","text":"hi"}]}}'
        event = parse_stream_line(line)
        assert event.counts_for_rotation is True

    def test_counts_tool_result_events(self) -> None:
        """tool_result events are countable."""
        line = '{"type":"tool_result","content":"ok","is_error":false}'
        event = parse_stream_line(line)
        assert event.counts_for_rotation is True

    def test_system_event_not_counted(self) -> None:
        """system events don't count for rotation."""
        line = '{"type":"system","message":"info"}'
        event = parse_stream_line(line)
        assert event.counts_for_rotation is False


class TestStatusBlock:
    """Test detection of phase completion status blocks."""

    def test_detect_complete_status(self) -> None:
        """Detect complete status block in assistant text."""
        text = 'Some discussion.\n{"status": "complete", "summary": "Done", "artifacts": ["/docs/design.md"]}'
        block = StatusBlock.from_text(text)
        assert block is not None
        assert block.status == "complete"
        assert block.summary == "Done"
        assert block.artifacts == ["/docs/design.md"]

    def test_detect_escalate_status(self) -> None:
        """Detect escalate status block."""
        text = '{"status": "escalate", "reason": "Cannot proceed"}'
        block = StatusBlock.from_text(text)
        assert block is not None
        assert block.status == "escalate"
        assert block.reason == "Cannot proceed"

    def test_detect_blocked_status(self) -> None:
        """Detect blocked status block."""
        text = '{"status":"blocked","reason":"Need clarification"}'
        block = StatusBlock.from_text(text)
        assert block is not None
        assert block.status == "blocked"

    def test_no_status_block(self) -> None:
        """Returns None when no status block present."""
        assert StatusBlock.from_text("Just regular text") is None
        assert StatusBlock.from_text('{"key": "value"}') is None

    def test_status_block_with_surrounding_text(self) -> None:
        """Extracts status block even with surrounding text."""
        text = 'Here is my analysis.\n\n{"status": "complete", "summary": "All done"}\n\nExtra text.'
        block = StatusBlock.from_text(text)
        assert block is not None
        assert block.status == "complete"
