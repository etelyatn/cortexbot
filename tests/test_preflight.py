"""Tests for preflight health checks."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from cortexbot.health.preflight import (
    check_editor_alive,
    check_git_branch,
    PreflightResult,
)


class TestCheckEditorAlive:
    """Test editor process health via port file."""

    def test_passes_with_valid_port_file(self, tmp_dir: Path) -> None:
        """Port file with live PID passes."""
        saved_dir = tmp_dir / "Saved"
        saved_dir.mkdir()
        (saved_dir / "CortexPort-12345.txt").write_text("8742")

        with patch("cortexbot.health.preflight._pid_alive", return_value=True):
            result = check_editor_alive(tmp_dir)
            assert result.passed is True

    def test_fails_with_no_port_file(self, tmp_dir: Path) -> None:
        """No port file means editor not running."""
        (tmp_dir / "Saved").mkdir()
        result = check_editor_alive(tmp_dir)
        assert result.passed is False

    def test_fails_with_dead_pid(self, tmp_dir: Path) -> None:
        """Port file with dead PID fails."""
        saved_dir = tmp_dir / "Saved"
        saved_dir.mkdir()
        (saved_dir / "CortexPort-99999.txt").write_text("8742")

        with patch("cortexbot.health.preflight._pid_alive", return_value=False):
            result = check_editor_alive(tmp_dir)
            assert result.passed is False


class TestCheckGitBranch:
    """Test git branch verification."""

    @patch("cortexbot.health.preflight._get_current_branch")
    def test_passes_on_correct_branch(self, mock_branch: MagicMock, tmp_dir: Path) -> None:
        mock_branch.return_value = "task/123-my-task"
        result = check_git_branch(tmp_dir, expected_branch="task/123-my-task")
        assert result.passed is True

    @patch("cortexbot.health.preflight._get_current_branch")
    def test_fails_on_wrong_branch(self, mock_branch: MagicMock, tmp_dir: Path) -> None:
        mock_branch.return_value = "main"
        result = check_git_branch(tmp_dir, expected_branch="task/123-my-task")
        assert result.passed is False
        assert "main" in result.reason
