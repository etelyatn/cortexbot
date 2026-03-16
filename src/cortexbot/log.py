"""Invocation logging — captures full stream-json output per invocation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class InvocationLogger:
    """Write stream-json lines to per-invocation log files.

    Files stored at: {base_dir}/logs/invocations/{date}/{task_id}_{phase}_{timestamp}.jsonl
    """

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def create_log(self, task_id: int, phase: str) -> Path:
        """Create a new invocation log file and return its path."""
        now = datetime.now(timezone.utc)
        date_dir = self._base_dir / "logs" / "invocations" / now.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{task_id}_{phase}_{now.strftime('%H%M%S')}.jsonl"
        path = date_dir / filename
        path.touch()

        logger.debug("Created invocation log: %s", path)
        return path

    def append_line(self, log_path: Path, line: str) -> None:
        """Append a line to an invocation log."""
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
            if not line.endswith("\n"):
                f.write("\n")

    def cleanup_old_logs(self, retention_days: int) -> int:
        """Delete invocation logs older than retention_days.

        Returns:
            Number of files deleted
        """
        logs_dir = self._base_dir / "logs" / "invocations"
        if not logs_dir.exists():
            return 0

        cutoff = datetime.now(timezone.utc)
        deleted = 0

        for date_dir in logs_dir.iterdir():
            if not date_dir.is_dir():
                continue
            try:
                dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                age_days = (cutoff - dir_date).days
                if age_days > retention_days:
                    for f in date_dir.iterdir():
                        f.unlink()
                        deleted += 1
                    date_dir.rmdir()
            except ValueError:
                continue

        return deleted
