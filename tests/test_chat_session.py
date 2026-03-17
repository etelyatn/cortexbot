from cortexbot.chat.session import ChatSession


def test_chat_session_creation():
    session = ChatSession(
        session_id="abc-123",
        project="sandbox",
        telegram_chat_id=-100123,
        telegram_thread_id=456,
    )
    assert session.message_count == 0
    assert session.tokens_used == 0
    assert session.subprocess_pid is None


def test_chat_session_serialization():
    session = ChatSession(
        session_id="abc",
        project="sandbox",
        telegram_chat_id=-100,
        telegram_thread_id=42,
        message_count=5,
        tokens_used=1234,
    )
    d = session.to_dict()
    restored = ChatSession.from_dict(d)
    assert restored.session_id == "abc"
    assert restored.message_count == 5
    assert restored.tokens_used == 1234


def test_chat_session_is_expired():
    from datetime import datetime, timezone, timedelta
    old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    session = ChatSession(
        session_id="x", project="p",
        telegram_chat_id=-1, telegram_thread_id=1,
        last_activity=old,
    )
    assert session.is_expired(timeout_seconds=7200) is True


def test_chat_session_not_expired():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    session = ChatSession(
        session_id="x", project="p",
        telegram_chat_id=-1, telegram_thread_id=1,
        last_activity=now,
    )
    assert session.is_expired(timeout_seconds=7200) is False
