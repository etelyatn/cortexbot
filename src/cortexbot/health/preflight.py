"""Pre-flight health checks before each phase invocation."""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)


@dataclass
class PreflightResult:
    """Result of a preflight check."""

    passed: bool
    reason: str = ""


def _pid_alive(pid: int) -> bool:
    """Check if a process with given PID is running."""
    try:
        proc = psutil.Process(pid)
        return proc.is_running()
    except psutil.NoSuchProcess:
        return False


def _get_current_branch(project_path: Path) -> str | None:
    """Get current git branch name."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            cwd=str(project_path),
            timeout=5,
        )
        return result.stdout.strip() or None
    except (subprocess.SubprocessError, OSError):
        return None


def check_editor_alive(project_path: Path) -> PreflightResult:
    """Check if Unreal Editor is running via CortexPort-{PID}.txt.

    Looks for port files in {project_path}/Saved/ and verifies the
    PID in the filename is alive.
    """
    saved_dir = project_path / "Saved"
    if not saved_dir.exists():
        return PreflightResult(passed=False, reason="Saved/ directory not found")

    port_files = list(saved_dir.glob("CortexPort-*.txt"))
    if not port_files:
        return PreflightResult(
            passed=False, reason="No CortexPort-*.txt found — is the editor running?"
        )

    for pf in port_files:
        match = re.search(r"CortexPort-(\d+)\.txt", pf.name)
        if match:
            pid = int(match.group(1))
            if _pid_alive(pid):
                return PreflightResult(passed=True)

    return PreflightResult(
        passed=False, reason="Editor PID(s) from port files are not running"
    )


def check_git_branch(
    project_path: Path, expected_branch: str
) -> PreflightResult:
    """Verify git is on the expected branch."""
    current = _get_current_branch(project_path)
    if current is None:
        return PreflightResult(passed=False, reason="Could not determine current git branch")

    if current != expected_branch:
        return PreflightResult(
            passed=False,
            reason=f"On branch '{current}', expected '{expected_branch}'",
        )

    return PreflightResult(passed=True)
