"""Tests for crash recovery on startup."""

from pathlib import Path

import pytest

from cortexbot.memory.store import TaskStore
from cortexbot.orchestrator.task_manager import TaskState
from cortexbot.main import recover_interrupted_tasks


@pytest.fixture
def store_with_tasks(tmp_path: Path) -> TaskStore:
    """Store with a mix of task states."""
    store = TaskStore(base_dir=tmp_path)

    # Normal completed task
    t1 = TaskState(task_id="1", project="p", description="Done")
    t1.status = "completed"
    store.save_task(t1)

    # Active task with dead PID
    t2 = TaskState(task_id="2", project="p", description="Interrupted")
    t2.status = "active"
    t2.subprocess_pid = 999999  # non-existent PID
    store.save_task(t2)

    # Active task without PID (normal)
    t3 = TaskState(task_id="3", project="p", description="Pending")
    t3.status = "active"
    store.save_task(t3)

    return store


@pytest.mark.asyncio
class TestCrashRecovery:
    """Test interrupted task detection on startup."""

    async def test_detects_interrupted_tasks(self, store_with_tasks: TaskStore) -> None:
        """Finds tasks with active status and dead PIDs."""
        interrupted = await recover_interrupted_tasks(store_with_tasks)
        assert len(interrupted) == 1
        assert interrupted[0].task_id == "2"

    async def test_clears_dead_pid(self, store_with_tasks: TaskStore) -> None:
        """Interrupted tasks have PID cleared and last_error set."""
        await recover_interrupted_tasks(store_with_tasks)
        task = store_with_tasks.load_task("2")
        assert task.subprocess_pid is None
        assert task.session_id is None
        assert task.last_error is not None
        # V2: task stays active (will resume from last artifact)
        assert task.status == "active"

    async def test_no_interrupted_tasks(self, tmp_path: Path) -> None:
        """Returns empty list when no tasks are interrupted."""
        store = TaskStore(base_dir=tmp_path)
        t = TaskState(task_id="1", project="p", description="OK")
        store.save_task(t)
        interrupted = await recover_interrupted_tasks(store)
        assert interrupted == []
