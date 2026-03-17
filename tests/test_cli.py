"""Tests for Claude CLI invocation and flag assembly."""

import pytest

from cortexbot.claude.cli import build_invocation


def test_pipeline_invocation_new_session():
    """Pipeline sessions use --session-id, --append-system-prompt, --allowedTools."""
    inv = build_invocation(
        prompt="test prompt",
        session_id="abc-123",
        action="plan",
        mcp_config=".mcp.json",
        system_prompt_appendix="status block contract here",
        allowed_tools=["Read", "Glob", "Grep", "Write", "Edit"],
    )
    args = inv.args
    assert "-p" in args
    assert "test prompt" in args
    assert "--session-id" in args
    assert "abc-123" in args
    assert "--append-system-prompt" in args
    assert "--allowedTools" in args
    assert "--output-format" in args
    assert "stream-json" in args
    assert "--dangerously-skip-permissions" in args
    assert "--mcp-config" in args
    # No --max-budget-usd
    assert "--max-budget-usd" not in args


def test_chat_invocation_first_message():
    """Chat first message uses --session-id, no --allowedTools, no --append-system-prompt."""
    inv = build_invocation(
        prompt="Hello from chat",
        session_id="chat-uuid",
        action="chat",
        mcp_config=".mcp.json",
    )
    args = inv.args
    assert "--session-id" in args
    assert "--allowedTools" not in args
    assert "--append-system-prompt" not in args


def test_chat_invocation_resume():
    """Chat resume uses --resume instead of --session-id."""
    inv = build_invocation(
        prompt="Follow up message",
        session_id="chat-uuid",
        action="chat",
        mcp_config=".mcp.json",
        resume=True,
    )
    args = inv.args
    assert "--resume" in args
    assert "chat-uuid" in args
    assert "--session-id" not in args
