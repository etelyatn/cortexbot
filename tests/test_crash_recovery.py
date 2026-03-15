"""Tests for crash recovery on startup."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from cortexbot.memory.store import TaskStore
from cortexbot.orchestrator.task_manager import TaskState
from cortexbot.main import recover_interrupted_tasks


@pytest.fixture
def store_with_tasks(tmp_dir: Path) -> TaskStore:
    """Store with a mix of task states."""
    store = TaskStore(base_dir=tmp_dir)

    # Normal completed task
    t1 = TaskState.create(thread_id=1, title="Done", project="p", budget_usd=5.0)
    t1.current_phase_status = "completed"
    store.save_task(t1)

    # Interrupted task (PID gone)
    t2 = TaskState.create(thread_id=2, title="Interrupted", project="p", budget_usd=5.0)
    t2.current_phase_status = "in_progress"
    t2.subprocess_pid = 999999  # non-existent PID
    store.save_task(t2)

    # Pending task (normal)
    t3 = TaskState.create(thread_id=3, title="Pending", project="p", budget_usd=5.0)
    t3.current_phase_status = "pending"
    store.save_task(t3)

    return store


@pytest.mark.asyncio
class TestCrashRecovery:
    """Test interrupted task detection on startup."""

    async def test_detects_interrupted_tasks(self, store_with_tasks: TaskStore) -> None:
        """Finds tasks with in_progress status and dead PIDs."""
        interrupted = await recover_interrupted_tasks(store_with_tasks)
        assert len(interrupted) == 1
        assert interrupted[0].thread_id == 2

    async def test_marks_interrupted(self, store_with_tasks: TaskStore) -> None:
        """Interrupted tasks are marked as interrupted on disk."""
        await recover_interrupted_tasks(store_with_tasks)
        task = store_with_tasks.load_task(2)
        assert task.current_phase_status == "interrupted"
        assert task.subprocess_pid is None

    async def test_no_interrupted_tasks(self, tmp_dir: Path) -> None:
        """Returns empty list when no tasks are interrupted."""
        store = TaskStore(base_dir=tmp_dir)
        t = TaskState.create(thread_id=1, title="OK", project="p", budget_usd=5.0)
        store.save_task(t)
        interrupted = await recover_interrupted_tasks(store)
        assert interrupted == []
