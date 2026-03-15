"""Allowed tools per phase for --allowedTools flag.

Top-level Claude Code tools only. Bash restrictions (e.g. "no build" in Design)
are prompt-enforced, not structurally enforced.
"""

from __future__ import annotations

# MCP tools that are read-only (safe for design/plan phases)
_MCP_READ_ONLY = [
    "mcp__cortex_mcp__reflect_cmd",
    "mcp__cortex_mcp__data_cmd",
    "mcp__cortex_mcp__graph_cmd",
    "mcp__cortex_mcp__query_class_context",
    "mcp__cortex_mcp__query_class_detail",
    "mcp__cortex_mcp__query_class_hierarchy",
    "mcp__cortex_mcp__query_overrides",
    "mcp__cortex_mcp__query_usages",
    "mcp__cortex_mcp__get_dependencies",
    "mcp__cortex_mcp__get_referencers",
    "mcp__cortex_mcp__reflect_cache_status",
    "mcp__cortex_mcp__scan_project",
]

# MCP tools for test/QA
_MCP_QA = [
    "mcp__cortex_mcp__qa_cmd",
    "mcp__cortex_mcp__qa_test_step",
    "mcp__cortex_mcp__editor_cmd",
    "mcp__cortex_mcp__editor_restart",
    "mcp__cortex_mcp__reflect_cmd",
]

# All MCP tools (implement has full access)
_MCP_ALL = _MCP_READ_ONLY + [
    "mcp__cortex_mcp__core_cmd",
    "mcp__cortex_mcp__editor_cmd",
    "mcp__cortex_mcp__editor_restart",
    "mcp__cortex_mcp__blueprint_cmd",
    "mcp__cortex_mcp__blueprint_compose",
    "mcp__cortex_mcp__material_cmd",
    "mcp__cortex_mcp__material_compose",
    "mcp__cortex_mcp__material_instance_compose",
    "mcp__cortex_mcp__level_cmd",
    "mcp__cortex_mcp__level_compose",
    "mcp__cortex_mcp__umg_cmd",
    "mcp__cortex_mcp__widget_compose",
    "mcp__cortex_mcp__scenario_compose",
    "mcp__cortex_mcp__schema_generate",
    "mcp__cortex_mcp__qa_cmd",
    "mcp__cortex_mcp__qa_test_step",
    "mcp__cortex_mcp__impact_analysis",
    "mcp__cortex_mcp__rebuild_graph_cache",
]

PHASE_TOOLS: dict[str, list[str]] = {
    "design": ["Read", "Glob", "Grep", "Write", "Edit", "Bash", "Agent"] + _MCP_READ_ONLY,
    "plan": ["Read", "Glob", "Grep", "Write", "Edit", "Bash", "Agent"] + _MCP_READ_ONLY,
    "implement": ["Read", "Glob", "Grep", "Write", "Edit", "Bash", "Agent"] + _MCP_ALL,
    "test": ["Read", "Glob", "Grep", "Bash", "Agent"] + _MCP_QA,
    "merge": ["Read", "Glob", "Grep", "Bash"],
}


def get_allowed_tools(phase: str) -> list[str]:
    """Get the allowed tools list for a phase.

    Args:
        phase: Phase name

    Returns:
        List of tool names for --allowedTools flag
    """
    return PHASE_TOOLS.get(phase, [])
