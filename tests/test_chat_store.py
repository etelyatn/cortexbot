from pathlib import Path
import pytest
from cortexbot.chat.session import ChatSession
from cortexbot.chat.store import ChatSessionStore


@pytest.fixture
def store(tmp_path: Path) -> ChatSessionStore:
    return ChatSessionStore(base_dir=tmp_path)


def test_save_and_load(store):
    session = ChatSession(session_id="abc", project="p", telegram_chat_id=-1, telegram_thread_id=1)
    store.save(session)
    loaded = store.load("abc")
    assert loaded is not None
    assert loaded.session_id == "abc"


def test_load_nonexistent(store):
    assert store.load("nope") is None


def test_find_by_thread(store):
    s = ChatSession(session_id="x", project="p", telegram_chat_id=-100, telegram_thread_id=42)
    store.save(s)
    found = store.find_by_thread(-100, 42)
    assert found is not None
    assert found.session_id == "x"


def test_list_sessions(store):
    s1 = ChatSession(session_id="a", project="p", telegram_chat_id=-1, telegram_thread_id=1)
    s2 = ChatSession(session_id="b", project="p", telegram_chat_id=-1, telegram_thread_id=2)
    store.save(s1)
    store.save(s2)
    assert len(store.list_sessions()) == 2


def test_delete(store):
    s = ChatSession(session_id="del", project="p", telegram_chat_id=-1, telegram_thread_id=1)
    store.save(s)
    store.delete("del")
    assert store.load("del") is None
