"""Claude Code CLI invocation and subprocess management."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ClaudeInvocation:
    """Represents a prepared CLI invocation."""

    args: list[str]
    cwd: str


def build_invocation(
    *,
    binary: str,
    prompt: str,
    project_path: str,
    session_id: str | None = None,
    resume_session_id: str | None = None,
    system_prompt: str | None = None,
    max_budget_usd: float | None = None,
    allowed_tools: list[str] | None = None,
    mcp_config: str | None = None,
) -> ClaudeInvocation:
    """Build CLI arguments for a Claude Code invocation.

    Args:
        binary: Path to claude binary
        prompt: User message / phase instruction
        project_path: Working directory for Claude
        session_id: New session UUID (mutually exclusive with resume_session_id)
        resume_session_id: Session UUID to resume (mutually exclusive with session_id)
        system_prompt: Text to append as system prompt
        max_budget_usd: Per-invocation cost cap
        allowed_tools: List of allowed tool names
        mcp_config: Path to .mcp.json

    Returns:
        ClaudeInvocation with args list and cwd
    """
    args = [binary, "--output-format", "stream-json"]

    if resume_session_id:
        # Resume mode: prompt is sent as a continuation message, not -p
        args.extend(["--resume", resume_session_id])
    else:
        # Print mode: single prompt invocation
        args.append("-p")
        if session_id:
            args.extend(["--session-id", session_id])

    if system_prompt:
        args.extend(["--append-system-prompt", system_prompt])

    if max_budget_usd is not None:
        args.extend(["--max-budget-usd", str(max_budget_usd)])

    if allowed_tools:
        args.extend(["--allowedTools", ",".join(allowed_tools)])

    if mcp_config:
        args.extend(["--mcp-config", mcp_config])

    args.append("--dangerously-skip-permissions")
    args.append(prompt)

    return ClaudeInvocation(args=args, cwd=project_path)


async def run_claude(
    invocation: ClaudeInvocation,
) -> asyncio.subprocess.Process:
    """Spawn Claude Code as an asyncio subprocess.

    Args:
        invocation: Prepared invocation with args and cwd

    Returns:
        asyncio subprocess handle (stdout is piped for stream parsing)
    """
    logger.info("Spawning Claude: %s", " ".join(invocation.args[:6]) + "...")
    process = await asyncio.create_subprocess_exec(
        *invocation.args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=invocation.cwd,
    )
    return process
