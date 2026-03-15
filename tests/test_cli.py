"""Tests for Claude CLI invocation and flag assembly."""

import pytest

from cortexbot.claude.cli import ClaudeInvocation, build_invocation


class TestBuildInvocation:
    """Test CLI flag assembly."""

    def test_minimal_invocation(self) -> None:
        """Minimal invocation has required flags."""
        inv = build_invocation(
            binary="claude",
            prompt="Do something",
            project_path="/tmp/project",
        )
        args = inv.args
        assert args[0] == "claude"
        assert "-p" in args
        assert "--output-format" in args
        idx = args.index("--output-format")
        assert args[idx + 1] == "stream-json"
        assert "--dangerously-skip-permissions" in args
        assert "Do something" in args

    def test_session_id(self) -> None:
        """Session ID flag included when provided."""
        inv = build_invocation(
            binary="claude",
            prompt="test",
            project_path="/tmp/project",
            session_id="abc-123",
        )
        assert "--session-id" in inv.args
        idx = inv.args.index("--session-id")
        assert inv.args[idx + 1] == "abc-123"

    def test_resume(self) -> None:
        """Resume flag replaces session-id."""
        inv = build_invocation(
            binary="claude",
            prompt="test",
            project_path="/tmp/project",
            resume_session_id="abc-123",
        )
        assert "--resume" in inv.args
        idx = inv.args.index("--resume")
        assert inv.args[idx + 1] == "abc-123"
        assert "--session-id" not in inv.args

    def test_append_system_prompt(self) -> None:
        """System prompt appended when provided."""
        inv = build_invocation(
            binary="claude",
            prompt="test",
            project_path="/tmp/project",
            system_prompt="You are a bot.",
        )
        assert "--append-system-prompt" in inv.args
        idx = inv.args.index("--append-system-prompt")
        assert inv.args[idx + 1] == "You are a bot."

    def test_max_budget(self) -> None:
        """Budget flag included when provided."""
        inv = build_invocation(
            binary="claude",
            prompt="test",
            project_path="/tmp/project",
            max_budget_usd=5.0,
        )
        assert "--max-budget-usd" in inv.args
        idx = inv.args.index("--max-budget-usd")
        assert inv.args[idx + 1] == "5.0"

    def test_allowed_tools(self) -> None:
        """Allowed tools flag included when provided."""
        inv = build_invocation(
            binary="claude",
            prompt="test",
            project_path="/tmp/project",
            allowed_tools=["Read", "Write", "Bash"],
        )
        assert "--allowedTools" in inv.args
        idx = inv.args.index("--allowedTools")
        assert inv.args[idx + 1] == "Read,Write,Bash"

    def test_mcp_config(self) -> None:
        """MCP config flag included when provided."""
        inv = build_invocation(
            binary="claude",
            prompt="test",
            project_path="/tmp/project",
            mcp_config=".mcp.json",
        )
        assert "--mcp-config" in inv.args

    def test_cwd_set(self) -> None:
        """Working directory set to project path."""
        inv = build_invocation(
            binary="claude",
            prompt="test",
            project_path="/tmp/myproject",
        )
        assert inv.cwd == "/tmp/myproject"
