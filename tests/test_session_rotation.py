from cortexbot.memory.session_rotation import should_rotate


def test_execute_rotation():
    assert should_rotate("execute", 100) is True
    assert should_rotate("execute", 99) is False


def test_implement_rotation():
    assert should_rotate("implement", 100) is True


def test_non_execute_never_rotates():
    assert should_rotate("brainstorm", 200) is False
    assert should_rotate("plan", 200) is False
    assert should_rotate("review", 200) is False


def test_fix_actions_rotate():
    assert should_rotate("fix-review", 100) is True
    assert should_rotate("fix-tests", 100) is True
