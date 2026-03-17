import pytest
from cortexbot.orchestrator.task_manager import (
    TaskState, ReviewResult, TestResult, SessionRecord,
)


def test_next_action_brainstorm():
    """No spec -> brainstorm."""
    task = TaskState(task_id="123", project="sandbox", description="Add inventory")
    assert task.next_action == "brainstorm"


def test_next_action_plan():
    """Has spec, no plan -> plan."""
    task = TaskState(task_id="123", project="sandbox", description="test")
    task.spec_path = "docs/superpowers/specs/test.md"
    assert task.next_action == "plan"


def test_next_action_implement():
    """Has spec + plan, not implemented -> implement."""
    task = TaskState(task_id="123", project="sandbox", description="test")
    task.spec_path = "docs/specs/test.md"
    task.plan_path = "docs/plans/test.md"
    assert task.next_action == "implement"


def test_next_action_review():
    """Implementation complete, no review -> review."""
    task = TaskState(task_id="123", project="sandbox", description="test")
    task.spec_path = "s"
    task.plan_path = "p"
    task.implementation_complete = True
    assert task.next_action == "review"


def test_next_action_test():
    """Review passed, no test -> test."""
    task = TaskState(task_id="123", project="sandbox", description="test")
    task.spec_path = "s"
    task.plan_path = "p"
    task.implementation_complete = True
    task.review_result = ReviewResult(passed=True, feedback_summary="LGTM")
    assert task.next_action == "test"


def test_next_action_finish():
    """Review passed + tests passed -> finish."""
    task = TaskState(task_id="123", project="sandbox", description="test")
    task.spec_path = "s"
    task.plan_path = "p"
    task.implementation_complete = True
    task.review_result = ReviewResult(passed=True, feedback_summary="LGTM")
    task.test_result = TestResult(passed=True, summary="47 passed")
    assert task.next_action == "finish"


def test_next_action_fix_review():
    """Review failed, under max cycles -> fix-review."""
    task = TaskState(task_id="123", project="sandbox", description="test")
    task.spec_path = "s"
    task.plan_path = "p"
    task.implementation_complete = True
    task.review_result = ReviewResult(passed=False, feedback_summary="3 issues")
    task.review_cycle = 1
    assert task.next_action == "fix-review"


def test_next_action_fix_tests():
    """Tests failed, under max cycles -> fix-tests."""
    task = TaskState(task_id="123", project="sandbox", description="test")
    task.spec_path = "s"
    task.plan_path = "p"
    task.implementation_complete = True
    task.review_result = ReviewResult(passed=True, feedback_summary="ok")
    task.test_result = TestResult(passed=False, summary="2 failed", failed_tests=["test_a"])
    task.test_cycle = 1
    assert task.next_action == "fix-tests"


def test_next_action_escalate_review():
    """Review failed at max cycles -> escalate."""
    task = TaskState(task_id="123", project="sandbox", description="test")
    task.review_result = ReviewResult(passed=False, feedback_summary="issues")
    task.review_cycle = 3
    task.max_cycles = 3
    assert task.next_action == "escalate"


def test_next_action_escalate_tests():
    """Tests failed at max cycles -> escalate."""
    task = TaskState(task_id="123", project="sandbox", description="test")
    task.test_result = TestResult(passed=False, summary="fail", failed_tests=["x"])
    task.test_cycle = 3
    task.max_cycles = 3
    assert task.next_action == "escalate"


def test_next_action_budget_exceeded():
    """Over token budget -> budget-exceeded."""
    task = TaskState(task_id="123", project="sandbox", description="test")
    task.token_budget = 100000
    task.tokens_used = 100001
    assert task.next_action == "budget-exceeded"


def test_next_action_paused():
    """Paused status -> paused."""
    task = TaskState(task_id="123", project="sandbox", description="test")
    task.status = "paused"
    assert task.next_action == "paused"


def test_next_action_completed_returns_paused():
    """Completed status also returns paused (non-active)."""
    task = TaskState(task_id="123", project="sandbox", description="test")
    task.status = "completed"
    assert task.next_action == "paused"


def test_next_action_cancelled_returns_paused():
    """Cancelled status also returns paused (non-active)."""
    task = TaskState(task_id="123", project="sandbox", description="test")
    task.status = "cancelled"
    assert task.next_action == "paused"


def test_serialization_round_trip():
    """TaskState serializes to dict and back."""
    task = TaskState(task_id="42", project="sandbox", description="Build it")
    task.spec_path = "spec.md"
    task.review_result = ReviewResult(passed=False, feedback_summary="fix x")
    task.sessions.append(SessionRecord(session_id="abc", action="brainstorm", started_at="2026-01-01"))

    d = task.to_dict()
    restored = TaskState.from_dict(d)

    assert restored.task_id == "42"
    assert restored.spec_path == "spec.md"
    assert restored.review_result.passed is False
    assert restored.review_result.feedback_summary == "fix x"
    assert len(restored.sessions) == 1
    assert restored.sessions[0].session_id == "abc"
