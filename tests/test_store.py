"""Tests for filesystem task state store."""

from pathlib import Path

import pytest

from cortexbot.memory.store import TaskStore
from cortexbot.orchestrator.task_manager import TaskState


@pytest.fixture
def store(tmp_dir: Path) -> TaskStore:
    """Create a TaskStore with tmp directory."""
    return TaskStore(base_dir=tmp_dir)


@pytest.fixture
def sample_task() -> TaskState:
    """Create a sample task."""
    return TaskState.create(
        thread_id=12345, title="Test task", project="sandbox", budget_usd=10.0
    )


class TestTaskStore:
    """Test atomic task state persistence."""

    def test_save_and_load(self, store: TaskStore, sample_task: TaskState) -> None:
        """Round-trip save and load."""
        store.save_task(sample_task)
        loaded = store.load_task(12345)
        assert loaded is not None
        assert loaded.thread_id == 12345
        assert loaded.title == "Test task"

    def test_load_nonexistent_returns_none(self, store: TaskStore) -> None:
        """Loading a non-existent task returns None."""
        assert store.load_task(99999) is None

    def test_save_creates_directory(self, tmp_dir: Path) -> None:
        """Save creates the tasks directory if missing."""
        store = TaskStore(base_dir=tmp_dir / "nested" / "dir")
        task = TaskState.create(
            thread_id=1, title="Test", project="p", budget_usd=5.0
        )
        store.save_task(task)
        assert store.load_task(1) is not None

    def test_list_tasks(self, store: TaskStore) -> None:
        """List all saved tasks."""
        t1 = TaskState.create(thread_id=1, title="One", project="p", budget_usd=5.0)
        t2 = TaskState.create(thread_id=2, title="Two", project="p", budget_usd=5.0)
        store.save_task(t1)
        store.save_task(t2)
        tasks = store.list_tasks()
        assert len(tasks) == 2
        ids = {t.thread_id for t in tasks}
        assert ids == {1, 2}

    def test_overwrite_existing(self, store: TaskStore, sample_task: TaskState) -> None:
        """Saving again overwrites previous state."""
        store.save_task(sample_task)
        sample_task.current_phase = "plan"
        store.save_task(sample_task)
        loaded = store.load_task(12345)
        assert loaded.current_phase == "plan"

    def test_delete_task(self, store: TaskStore, sample_task: TaskState) -> None:
        """Delete removes the task file."""
        store.save_task(sample_task)
        store.delete_task(12345)
        assert store.load_task(12345) is None

    def test_atomic_write_leaves_no_tmp(self, store: TaskStore, sample_task: TaskState) -> None:
        """After save, no .tmp file remains."""
        store.save_task(sample_task)
        tasks_dir = store._tasks_dir
        tmp_files = list(tasks_dir.glob("*.tmp"))
        assert tmp_files == []
