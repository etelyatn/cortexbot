"""Per-action tool restrictions for Claude Code sessions."""

from typing import Optional

# Base tool sets
_READ_ONLY = ["Read", "Glob", "Grep"]
_READ_WRITE = ["Read", "Glob", "Grep", "Write", "Edit"]
_ALL = ["Read", "Glob", "Grep", "Write", "Edit", "Bash", "Agent"]
_GIT_ONLY = ["Read", "Glob", "Grep", "Bash"]

# MCP tool patterns
_MCP_ALL = ["mcp__cortex_mcp__*"]

ACTION_TOOLS: dict[str, Optional[list[str]]] = {
    "brainstorm": _READ_ONLY,
    "brainstorm-spec": _READ_WRITE,
    "plan": _READ_WRITE,
    "execute": _ALL + _MCP_ALL,
    "implement": _ALL + _MCP_ALL,
    "fix-review": _ALL + _MCP_ALL,
    "fix-tests": _ALL + _MCP_ALL,
    "review": _READ_ONLY,
    "test": _ALL + _MCP_ALL,
    "finish": _GIT_ONLY,
    "chat": None,  # Full access — omit --allowedTools
}


def get_allowed_tools(action: str) -> Optional[list[str]]:
    """Return tool list for --allowedTools, or None to omit the flag."""
    return ACTION_TOOLS.get(action)
