"""Tests for per-phase tool allowlists."""

import pytest

from cortexbot.orchestrator.phase_tools import get_allowed_tools


class TestGetAllowedTools:
    """Test tool allowlist per phase."""

    def test_design_has_read_write_no_mcp_write(self) -> None:
        """Design phase has Read, Write, Edit but no write MCP tools."""
        tools = get_allowed_tools("design")
        assert "Read" in tools
        assert "Write" in tools
        assert "Edit" in tools
        assert "Bash" in tools
        assert "mcp__cortex_mcp__blueprint_cmd" not in tools

    def test_implement_has_all_tools(self) -> None:
        """Implement phase has full access including write MCP tools."""
        tools = get_allowed_tools("implement")
        assert "Read" in tools
        assert "Write" in tools
        assert "Bash" in tools
        assert "mcp__cortex_mcp__blueprint_cmd" in tools

    def test_test_has_no_write_edit(self) -> None:
        """Test phase cannot write or edit code."""
        tools = get_allowed_tools("test")
        assert "Read" in tools
        assert "Write" not in tools
        assert "Edit" not in tools

    def test_merge_is_minimal(self) -> None:
        """Merge phase has only Read, Glob, Grep, Bash."""
        tools = get_allowed_tools("merge")
        assert "Read" in tools
        assert "Bash" in tools
        assert "Write" not in tools
        assert "Agent" not in tools

    def test_unknown_phase_returns_empty(self) -> None:
        """Unknown phase returns empty list."""
        assert get_allowed_tools("nonexistent") == []
