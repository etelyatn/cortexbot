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

    def save(self, session: ChatSession) -> None:
        self._chats_dir.mkdir(parents=True, exist_ok=True)
        target = self._chats_dir / f"{session.session_id}.json"
        tmp = self._chats_dir / f"{session.session_id}.json.tmp"
        data = json.dumps(session.to_dict(), indent=2)
        tmp.write_text(data, encoding="utf-8")
        os.replace(str(tmp), str(target))

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
        for session in self.list_sessions():
            if session.telegram_chat_id == chat_id and session.telegram_thread_id == thread_id:
                return session
        return None

    def list_sessions(self) -> list[ChatSession]:
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
            target.unlink()
