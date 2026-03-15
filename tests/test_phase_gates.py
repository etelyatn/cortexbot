"""Tests for phase gate validation."""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from cortexbot.orchestrator.phase_gates import validate_gate, GateResult


class TestDesignGate:
    """Design phase gate: design doc exists in docs/."""

    def test_passes_when_doc_exists(self, tmp_dir: Path) -> None:
        """Gate passes when design doc artifact exists."""
        doc = tmp_dir / "docs" / "plans" / "design.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("# Design")
        result = validate_gate("design", tmp_dir, artifacts=["docs/plans/design.md"])
        assert result.passed is True

    def test_fails_when_doc_missing(self, tmp_dir: Path) -> None:
        """Gate fails when no design doc found."""
        result = validate_gate("design", tmp_dir, artifacts=[])
        assert result.passed is False
        assert "design doc" in result.reason.lower() or "artifact" in result.reason.lower()


class TestPlanGate:
    """Plan phase gate: impl guide exists in docs/."""

    def test_passes_when_guide_exists(self, tmp_dir: Path) -> None:
        doc = tmp_dir / "docs" / "plans" / "impl.md"
        doc.parent.mkdir(parents=True)
        doc.write_text("# Plan")
        result = validate_gate("plan", tmp_dir, artifacts=["docs/plans/impl.md"])
        assert result.passed is True

    def test_fails_when_guide_missing(self, tmp_dir: Path) -> None:
        result = validate_gate("plan", tmp_dir, artifacts=[])
        assert result.passed is False


class TestImplementGate:
    """Implement phase gate: git has committed changes on task branch."""

    @patch("cortexbot.orchestrator.phase_gates._git_has_commits")
    def test_passes_with_commits(self, mock_git: MagicMock, tmp_dir: Path) -> None:
        mock_git.return_value = True
        result = validate_gate("implement", tmp_dir, branch="task/1-test")
        assert result.passed is True

    @patch("cortexbot.orchestrator.phase_gates._git_has_commits")
    def test_fails_without_commits(self, mock_git: MagicMock, tmp_dir: Path) -> None:
        mock_git.return_value = False
        result = validate_gate("implement", tmp_dir, branch="task/1-test")
        assert result.passed is False


class TestTestGate:
    """Test phase gate: tests pass (based on Claude's status block, not re-run)."""

    def test_passes_with_complete_status(self, tmp_dir: Path) -> None:
        """Gate passes when status block says complete."""
        result = validate_gate("test", tmp_dir, status_complete=True)
        assert result.passed is True

    def test_fails_without_complete_status(self, tmp_dir: Path) -> None:
        result = validate_gate("test", tmp_dir, status_complete=False)
        assert result.passed is False


class TestMergeGate:
    """Merge phase gate: branch merged or PR created."""

    def test_passes_with_complete_status(self, tmp_dir: Path) -> None:
        result = validate_gate("merge", tmp_dir, status_complete=True)
        assert result.passed is True
