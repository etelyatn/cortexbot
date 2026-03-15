"""Phase gate validation — deliverable checks between phases."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """Result of a phase gate validation."""

    passed: bool
    reason: str = ""


def _git_has_commits(project_path: Path, branch: str, default_branch: str = "main") -> bool:
    """Check if branch has commits diverging from default branch."""
    try:
        result = subprocess.run(
            ["git", "log", f"{default_branch}..{branch}", "--oneline"],
            capture_output=True,
            text=True,
            cwd=str(project_path),
            timeout=10,
        )
        return bool(result.stdout.strip())
    except (subprocess.SubprocessError, OSError) as e:
        logger.warning("Git check failed: %s", e)
        return False


def validate_gate(
    phase: str,
    project_path: Path,
    *,
    artifacts: list[str] | None = None,
    branch: str | None = None,
    default_branch: str = "main",
    status_complete: bool | None = None,
) -> GateResult:
    """Validate the gate for a completed phase.

    Args:
        phase: The phase that just completed
        project_path: Path to the project root
        artifacts: List of artifact paths from the phase
        branch: Git branch name (for implement gate)
        status_complete: Whether Claude reported status=complete (for test/merge gates)

    Returns:
        GateResult with passed flag and reason if failed
    """
    artifacts = artifacts or []

    if phase == "design":
        for artifact in artifacts:
            full_path = project_path / artifact
            if full_path.exists():
                return GateResult(passed=True)
        return GateResult(
            passed=False,
            reason="Design gate failed: no design doc artifact found on disk",
        )

    elif phase == "plan":
        for artifact in artifacts:
            full_path = project_path / artifact
            if full_path.exists():
                return GateResult(passed=True)
        return GateResult(
            passed=False,
            reason="Plan gate failed: no implementation guide artifact found on disk",
        )

    elif phase == "implement":
        if branch and _git_has_commits(project_path, branch, default_branch):
            return GateResult(passed=True)
        return GateResult(
            passed=False,
            reason="Implement gate failed: no committed changes found on task branch",
        )

    elif phase == "test":
        if status_complete:
            return GateResult(passed=True)
        return GateResult(
            passed=False,
            reason="Test gate failed: tests did not report as passing",
        )

    elif phase == "merge":
        if status_complete:
            return GateResult(passed=True)
        return GateResult(
            passed=False,
            reason="Merge gate failed: branch not merged or PR not created",
        )

    return GateResult(passed=False, reason=f"Unknown phase: {phase}")
