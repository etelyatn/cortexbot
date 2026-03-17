"""Filesystem store for chat sessions."""

import json
import logging
import os
from pathlib import Path

from cortexbot.chat.session import ChatSession

logger = logging.getLogger(__name__)


class ChatSessionStore:
    def __init__(self, base_dir: Path) -> None:
        self._chats_dir = base_dir / "chats"
        # In-memory index: (chat_id, thread_id) -> session_id
        self._thread_index: dict[tuple[int, int], str] = {}
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Rebuild in-memory index from disk."""
        self._thread_index.clear()
        for session in self._list_from_disk():
            self._thread_index[(session.telegram_chat_id, session.telegram_thread_id)] = session.session_id

    def save(self, session: ChatSession) -> None:
        self._chats_dir.mkdir(parents=True, exist_ok=True)
        target = self._chats_dir / f"{session.session_id}.json"
        tmp = self._chats_dir / f"{session.session_id}.json.tmp"
        data = json.dumps(session.to_dict(), indent=2)
        tmp.write_text(data, encoding="utf-8")
        os.replace(str(tmp), str(target))
        self._thread_index[(session.telegram_chat_id, session.telegram_thread_id)] = session.session_id

    def load(self, session_id: str) -> ChatSession | None:
        target = self._chats_dir / f"{session_id}.json"
        if not target.exists():
            return None
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            return ChatSession.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Corrupt chat session %s: %s", session_id, e)
            return None

    def find_by_thread(self, chat_id: int, thread_id: int) -> ChatSession | None:
        session_id = self._thread_index.get((chat_id, thread_id))
        if session_id is None:
            return None
        return self.load(session_id)

    def list_sessions(self) -> list[ChatSession]:
        return self._list_from_disk()

    def _list_from_disk(self) -> list[ChatSession]:
        if not self._chats_dir.exists():
            return []
        sessions = []
        for path in self._chats_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sessions.append(ChatSession.from_dict(data))
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        return sessions

    def delete(self, session_id: str) -> None:
        target = self._chats_dir / f"{session_id}.json"
        if target.exists():
            # Remove from index before deleting file
            session = self.load(session_id)
            if session:
                self._thread_index.pop((session.telegram_chat_id, session.telegram_thread_id), None)
            target.unlink()
