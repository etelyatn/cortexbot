from cortexbot.claude.prompts import build_prompt, STATUS_BLOCK_CONTRACT
from cortexbot.orchestrator.task_manager import TaskState, ReviewResult, TestResult


def test_build_prompt_brainstorm():
    task = TaskState(task_id="1", project="sandbox", description="Add inventory system")
    result = build_prompt(task, "brainstorm")
    assert result.startswith("/brainstorming ")
    assert "Add inventory system" in result
    assert "USER MESSAGE" in result  # Fenced for prompt injection mitigation


def test_build_prompt_plan():
    task = TaskState(task_id="1", project="sandbox", description="test")
    task.spec_path = "docs/superpowers/specs/inventory.md"
    result = build_prompt(task, "plan")
    assert "/writing-plans" in result
    assert "docs/superpowers/specs/inventory.md" in result


def test_build_prompt_implement():
    task = TaskState(task_id="1", project="sandbox", description="test")
    task.plan_path = "docs/superpowers/plans/inventory.md"
    result = build_prompt(task, "implement")
    assert "/subagent-driven-development" in result
    assert "docs/superpowers/plans/inventory.md" in result


def test_build_prompt_fix_review():
    task = TaskState(task_id="1", project="sandbox", description="test")
    task.plan_path = "docs/plans/inv.md"
    task.review_result = ReviewResult(passed=False, feedback_summary="Fix type errors in Player.cpp")
    result = build_prompt(task, "fix-review")
    assert "/subagent-driven-development" in result
    assert "Fix type errors in Player.cpp" in result


def test_build_prompt_fix_tests():
    task = TaskState(task_id="1", project="sandbox", description="test")
    task.plan_path = "docs/plans/inv.md"
    task.test_result = TestResult(passed=False, summary="2 failed", failed_tests=["test_a", "test_b"])
    result = build_prompt(task, "fix-tests")
    assert "/subagent-driven-development" in result
    assert "test_a" in result
    assert "test_b" in result


def test_build_prompt_review():
    task = TaskState(task_id="1", project="sandbox", description="test")
    task.plan_path = "docs/plans/inv.md"
    task.branch_name = "task/1-inventory"
    result = build_prompt(task, "review")
    assert "/requesting-code-review" in result
    assert "task/1-inventory" in result


def test_build_prompt_finish():
    task = TaskState(task_id="1", project="sandbox", description="test")
    assert build_prompt(task, "finish") == "/finishing-a-development-branch"


def test_status_block_contract_contains_json_examples():
    assert '{"status": "complete"' in STATUS_BLOCK_CONTRACT
    assert '{"status": "escalate"' in STATUS_BLOCK_CONTRACT
    assert "review_passed" in STATUS_BLOCK_CONTRACT
