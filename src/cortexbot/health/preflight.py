"""V2 preflight checks — UEConnection-based editor health."""

import asyncio
from dataclasses import dataclass
from typing import Optional


@dataclass
class PreflightResult:
    passed: bool
    reason: str = ""


async def check_editor_alive(project_path: str) -> PreflightResult:
    """Check if editor is running and CortexCore TCP is reachable."""
    from cortexbot.services.unreal import check_ue_health
    result = await check_ue_health(project_path)
    if result["connected"]:
        return PreflightResult(passed=True)
    return PreflightResult(passed=False, reason=result.get("error", "Editor not reachable"))


async def check_git_branch(project_path: str, expected_branch: Optional[str] = None) -> PreflightResult:
    """Verify current git branch matches expected."""
    if expected_branch is None:
        return PreflightResult(passed=True)

    proc = await asyncio.create_subprocess_exec(
        "git", "rev-parse", "--abbrev-ref", "HEAD",
        cwd=project_path,
        stdout=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    current = stdout.decode().strip()

    if current == expected_branch:
        return PreflightResult(passed=True)
    return PreflightResult(
        passed=False,
        reason=f"Expected branch '{expected_branch}', on '{current}'",
    )
