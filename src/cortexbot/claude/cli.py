"""Claude Code CLI invocation builder."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ClaudeInvocation:
    args: list[str]
    cwd: Optional[str] = None


def build_invocation(
    prompt: str,
    session_id: str,
    action: str,
    mcp_config: str,
    system_prompt_appendix: Optional[str] = None,
    allowed_tools: Optional[list[str]] = None,
    resume: bool = False,
    claude_binary: str = "claude",
) -> ClaudeInvocation:
    """Build Claude Code CLI invocation for V2."""
    args = [claude_binary, "-p", prompt, "--output-format", "stream-json"]

    # Session: new or resume
    if resume:
        args.extend(["--resume", session_id])
    else:
        args.extend(["--session-id", session_id])

    # System prompt appendix (pipeline only, not chat)
    if system_prompt_appendix:
        args.extend(["--append-system-prompt", system_prompt_appendix])

    # Tool restrictions (None = omit for full access)
    if allowed_tools is not None:
        args.extend(["--allowedTools", ",".join(allowed_tools)])

    # MCP config
    args.extend(["--mcp-config", mcp_config])

    # Skip permissions
    args.append("--dangerously-skip-permissions")

    return ClaudeInvocation(args=args)


async def run_claude(invocation: ClaudeInvocation) -> asyncio.subprocess.Process:
    """Spawn Claude Code CLI subprocess."""
    logger.info("Spawning Claude: %s", " ".join(invocation.args[:6]) + "...")
    return await asyncio.create_subprocess_exec(
        *invocation.args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=invocation.cwd,
    )
