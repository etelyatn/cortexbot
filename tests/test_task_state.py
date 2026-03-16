"""Tests for TaskState data model."""

from datetime import datetime, timezone

import pytest

from cortexbot.orchestrator.task_manager import (
    Artifact,
    PhaseRecord,
    TaskState,
    PHASES,
    next_phase,
    slugify,
)


class TestSlugify:
    """Test title to branch slug conversion."""

    def test_simple_title(self) -> None:
        assert slugify("Add data tables") == "add-data-tables"

    def test_special_characters(self) -> None:
        assert slugify("Fix bug #123!") == "fix-bug-123"

    def test_long_title_truncated(self) -> None:
        long_title = "a" * 100
        result = slugify(long_title)
        assert len(result) <= 50

    def test_leading_trailing_hyphens(self) -> None:
        assert slugify("--hello--") == "hello"


class TestPhases:
    """Test phase ordering."""

    def test_phase_order(self) -> None:
        assert PHASES == ["design", "plan", "implement", "test", "merge"]

    def test_next_phase(self) -> None:
        assert next_phase("design") == "plan"
        assert next_phase("plan") == "implement"
        assert next_phase("implement") == "test"
        assert next_phase("test") == "merge"

    def test_next_phase_after_merge_is_none(self) -> None:
        assert next_phase("merge") is None


class TestTaskState:
    """Test TaskState creation and serialization."""

    def test_create_task(self) -> None:
        """Create a new task with defaults."""
        task = TaskState.create(
            thread_id=12345,
            title="Add data tables",
            project="sandbox",
            budget_usd=10.0,
        )
        assert task.thread_id == 12345
        assert task.title == "Add data tables"
        assert task.project == "sandbox"
        assert task.branch == "task/12345-add-data-tables"
        assert task.current_phase == "design"
        assert task.current_phase_status == "pending"
        assert task.autonomy == "supervised"
        assert task.budget_usd == 10.0
        assert task.retry_count == 0
        assert task.phase_history == []
        assert task.artifacts == []

    def test_to_dict_and_from_dict(self) -> None:
        """Round-trip serialization."""
        task = TaskState.create(
            thread_id=12345,
            title="Test task",
            project="sandbox",
            budget_usd=5.0,
        )
        data = task.to_dict()
        restored = TaskState.from_dict(data)
        assert restored.thread_id == task.thread_id
        assert restored.title == task.title
        assert restored.branch == task.branch
        assert restored.current_phase == task.current_phase

    def test_advance_phase(self) -> None:
        """Advancing phase moves to next and resets retry count."""
        task = TaskState.create(
            thread_id=1, title="Test", project="p", budget_usd=10.0
        )
        task.current_phase_status = "completed"
        task.retry_count = 2
        task.session_id = "some-session-id"
        task.session_event_count = 5

        task.advance_phase(summary="Design done", artifacts=["/docs/design.md"])

        assert task.current_phase == "plan"
        assert task.current_phase_status == "pending"
        assert task.retry_count == 0
        assert task.session_id is None
        assert task.session_event_count == 0
        assert len(task.phase_history) == 1
        assert task.phase_history[0].phase == "design"
        assert task.phase_history[0].summary == "Design done"

    def test_advance_past_merge_completes(self) -> None:
        """Advancing past merge marks task as complete."""
        task = TaskState.create(
            thread_id=1, title="Test", project="p", budget_usd=10.0
        )
        task.current_phase = "merge"
        task.current_phase_status = "completed"

        task.advance_phase(summary="PR created")

        assert task.current_phase == "merge"
        assert task.current_phase_status == "done"

    def test_artifact_tracking(self) -> None:
        """Artifacts can be added and queried."""
        task = TaskState.create(
            thread_id=1, title="Test", project="p", budget_usd=10.0
        )
        task.add_artifact("design_doc", "/docs/design.md", "design")
        assert len(task.artifacts) == 1
        assert task.artifacts[0].artifact_type == "design_doc"
        assert task.artifacts[0].path == "/docs/design.md"


class TestBudget:
    """Test budget tracking."""

    def test_deduct_cost(self) -> None:
        task = TaskState.create(thread_id=1, title="T", project="p", budget_usd=10.0)
        task.deduct_cost(3.5)
        assert task.budget_usd == 6.5

    def test_deduct_does_not_go_negative(self) -> None:
        task = TaskState.create(thread_id=1, title="T", project="p", budget_usd=2.0)
        task.deduct_cost(5.0)
        assert task.budget_usd == 0.0

    def test_add_budget(self) -> None:
        task = TaskState.create(thread_id=1, title="T", project="p", budget_usd=5.0)
        task.add_budget(3.0)
        assert task.budget_usd == 8.0

    def test_phase_budget_design_with_10(self) -> None:
        """Design phase with $10: 50% of remaining ($10) = $5, capped for this phase."""
        task = TaskState.create(thread_id=1, title="T", project="p", budget_usd=10.0)
        # design = index 0, 5 remaining phases
        # Formula: (remaining * 0.5) / remaining_phases, min $1
        # = ($10 * 0.5) / 5 phases = $1.00
        budget = task.calculate_phase_budget()
        assert budget == 1.0

    def test_phase_budget_last_phase(self) -> None:
        """Merge (last phase) gets all remaining budget."""
        task = TaskState.create(thread_id=1, title="T", project="p", budget_usd=3.0)
        task.current_phase = "merge"
        budget = task.calculate_phase_budget()
        assert budget == 3.0

    def test_phase_budget_minimum_is_one(self) -> None:
        """Phase budget never goes below $1."""
        task = TaskState.create(thread_id=1, title="T", project="p", budget_usd=0.50)
        budget = task.calculate_phase_budget()
        assert budget == 1.0
