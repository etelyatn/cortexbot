"""Filesystem store for task state with atomic writes."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from cortexbot.orchestrator.task_manager import TaskState

logger = logging.getLogger(__name__)


class TaskStore:
    """Persist TaskState as JSON files with atomic writes.

    Files stored at {base_dir}/tasks/{task_id}.json.
    Atomic writes: write to .tmp, then os.replace.
    """

    def __init__(self, base_dir: Path) -> None:
        self._tasks_dir = base_dir / "tasks"

    def save_task(self, task: TaskState) -> None:
        """Save task state atomically."""
        self._tasks_dir.mkdir(parents=True, exist_ok=True)

        target = self._tasks_dir / f"{task.task_id}.json"
        tmp = self._tasks_dir / f"{task.task_id}.json.tmp"

        data = json.dumps(task.to_dict(), indent=2)
        tmp.write_text(data, encoding="utf-8")
        os.replace(str(tmp), str(target))

        logger.debug("Saved task %s to %s", task.task_id, target)

    def load_task(self, task_id: str) -> TaskState | None:
        """Load task state from disk."""
        target = self._tasks_dir / f"{task_id}.json"
        tmp = self._tasks_dir / f"{task_id}.json.tmp"

        for path in (target, tmp):
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    return TaskState.from_dict(data)
                except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
                    logger.warning("Corrupt task file %s: %s", path, e)
                    continue

        return None

    def list_tasks(self) -> list[TaskState]:
        """List all saved tasks."""
        if not self._tasks_dir.exists():
            return []

        tasks = []
        for path in self._tasks_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                tasks.append(TaskState.from_dict(data))
            except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
                logger.warning("Skipping corrupt task file %s: %s", path, e)
        return tasks

    def delete_task(self, task_id: str) -> None:
        """Delete task state file."""
        target = self._tasks_dir / f"{task_id}.json"
        if target.exists():
            target.unlink()
            logger.debug("Deleted task %s", task_id)
