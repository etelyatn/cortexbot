from cortexbot.orchestrator.action_tools import get_allowed_tools


def test_brainstorm_questions_readonly():
    """Brainstorm (questions) session is read-only."""
    tools = get_allowed_tools("brainstorm")
    assert "Read" in tools
    assert "Glob" in tools
    assert "Grep" in tools
    assert "Write" not in tools
    assert "Bash" not in tools


def test_brainstorm_spec_can_write():
    """Brainstorm (spec) session can write files."""
    tools = get_allowed_tools("brainstorm-spec")
    assert "Write" in tools
    assert "Edit" in tools


def test_plan_no_bash():
    """Plan session has no Bash access."""
    tools = get_allowed_tools("plan")
    assert "Write" in tools
    assert "Bash" not in tools


def test_execute_full_access():
    """Execute has all tools."""
    tools = get_allowed_tools("execute")
    assert "Bash" in tools
    assert "Write" in tools
    assert "Read" in tools


def test_review_readonly():
    """Review is read-only."""
    tools = get_allowed_tools("review")
    assert "Read" in tools
    assert "Write" not in tools
    assert "Bash" not in tools


def test_finish_git_only():
    """Finish has Bash but limited to git (prompt-enforced)."""
    tools = get_allowed_tools("finish")
    assert "Bash" in tools
    assert "Read" in tools
    assert "Write" not in tools


def test_chat_returns_none():
    """Chat omits --allowedTools entirely (returns None)."""
    tools = get_allowed_tools("chat")
    assert tools is None
