"""Tests for filesystem task state store."""

import json
from pathlib import Path

import pytest

from cortexbot.memory.store import TaskStore
from cortexbot.orchestrator.task_manager import TaskState, ReviewResult


@pytest.fixture
def store(tmp_path: Path) -> TaskStore:
    """Create a TaskStore with tmp directory."""
    return TaskStore(base_dir=tmp_path)


@pytest.fixture
def sample_task() -> TaskState:
    """Create a sample V2 task."""
    return TaskState(task_id="42", project="sandbox", description="Test task")


class TestTaskStore:
    """Test atomic task state persistence."""

    def test_save_and_load(self, store: TaskStore, sample_task: TaskState) -> None:
        """Round-trip save and load."""
        store.save_task(sample_task)
        loaded = store.load_task("42")
        assert loaded is not None
        assert loaded.task_id == "42"
        assert loaded.description == "Test task"

    def test_load_nonexistent_returns_none(self, store: TaskStore) -> None:
        """Loading a non-existent task returns None."""
        assert store.load_task("99999") is None

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        """Save creates the tasks directory if missing."""
        store = TaskStore(base_dir=tmp_path / "nested" / "dir")
        task = TaskState(task_id="1", project="p", description="Test")
        store.save_task(task)
        assert store.load_task("1") is not None

    def test_list_tasks(self, store: TaskStore) -> None:
        """List all saved tasks."""
        t1 = TaskState(task_id="1", project="p", description="One")
        t2 = TaskState(task_id="2", project="p", description="Two")
        store.save_task(t1)
        store.save_task(t2)
        tasks = store.list_tasks()
        assert len(tasks) == 2
        ids = {t.task_id for t in tasks}
        assert ids == {"1", "2"}

    def test_overwrite_existing(self, store: TaskStore, sample_task: TaskState) -> None:
        """Saving again overwrites previous state."""
        store.save_task(sample_task)
        sample_task.spec_path = "spec.md"
        store.save_task(sample_task)
        loaded = store.load_task("42")
        assert loaded.spec_path == "spec.md"

    def test_delete_task(self, store: TaskStore, sample_task: TaskState) -> None:
        """Delete removes the task file."""
        store.save_task(sample_task)
        store.delete_task("42")
        assert store.load_task("42") is None

    def test_atomic_write_leaves_no_tmp(self, store: TaskStore, sample_task: TaskState) -> None:
        """After save, no .tmp file remains."""
        store.save_task(sample_task)
        tasks_dir = store._tasks_dir
        tmp_files = list(tasks_dir.glob("*.tmp"))
        assert tmp_files == []

    def test_load_falls_back_to_tmp(self, store: TaskStore, sample_task: TaskState) -> None:
        """Load falls back to .tmp if .json is corrupt."""
        store.save_task(sample_task)
        target = store._tasks_dir / "42.json"
        target.write_text("not valid json", encoding="utf-8")
        tmp = store._tasks_dir / "42.json.tmp"
        tmp.write_text(json.dumps(sample_task.to_dict()), encoding="utf-8")
        loaded = store.load_task("42")
        assert loaded is not None
        assert loaded.task_id == "42"

    def test_store_v2_task_with_artifacts(self, store: TaskStore) -> None:
        """TaskStore persists and loads V2 TaskState with artifacts correctly."""
        task = TaskState(task_id="99", project="sandbox", description="Build inventory")
        task.spec_path = "docs/specs/inventory.md"
        task.review_result = ReviewResult(passed=False, feedback_summary="fix types")
        task.tokens_used = 12345

        store.save_task(task)
        loaded = store.load_task("99")

        assert loaded is not None
        assert loaded.task_id == "99"
        assert loaded.spec_path == "docs/specs/inventory.md"
        assert loaded.review_result.feedback_summary == "fix types"
        assert loaded.tokens_used == 12345
