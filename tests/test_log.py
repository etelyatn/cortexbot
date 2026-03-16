"""Tests for invocation logging."""

from pathlib import Path

import pytest

from cortexbot.log import InvocationLogger


class TestInvocationLogger:
    """Test invocation log creation and management."""

    def test_create_log_returns_path(self, tmp_dir: Path) -> None:
        """create_log returns a path and creates the file."""
        logger = InvocationLogger(tmp_dir)
        path = logger.create_log(task_id=123, phase="design")
        assert path.exists()
        assert path.suffix == ".jsonl"
        assert "123" in path.name
        assert "design" in path.name

    def test_append_line(self, tmp_dir: Path) -> None:
        """Lines are appended with newline."""
        logger = InvocationLogger(tmp_dir)
        path = logger.create_log(task_id=1, phase="test")
        logger.append_line(path, '{"type":"assistant"}')
        logger.append_line(path, '{"type":"result"}')
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_cleanup_old_logs(self, tmp_dir: Path) -> None:
        """Cleanup deletes directories older than retention."""
        logger = InvocationLogger(tmp_dir)
        # Create a fake old log directory
        old_dir = tmp_dir / "logs" / "invocations" / "2020-01-01"
        old_dir.mkdir(parents=True)
        (old_dir / "1_design_120000.jsonl").write_text("old")
        deleted = logger.cleanup_old_logs(retention_days=30)
        assert deleted == 1
        assert not old_dir.exists()

    def test_cleanup_preserves_recent(self, tmp_dir: Path) -> None:
        """Cleanup preserves recent log directories."""
        logger = InvocationLogger(tmp_dir)
        path = logger.create_log(task_id=1, phase="design")
        deleted = logger.cleanup_old_logs(retention_days=30)
        assert deleted == 0
        assert path.exists()
