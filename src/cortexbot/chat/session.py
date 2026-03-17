"""Chat session data model."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ChatSession:
    session_id: str
    project: str
    telegram_chat_id: int
    telegram_thread_id: int
    message_count: int = 0
    tokens_used: int = 0
    subprocess_pid: Optional[int] = None
    last_activity: str = ""
    created_at: str = ""

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.last_activity:
            self.last_activity = now
        if not self.created_at:
            self.created_at = now

    def is_expired(self, timeout_seconds: int = 7200) -> bool:
        if not self.last_activity:
            return False
        last = datetime.fromisoformat(self.last_activity)
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed > timeout_seconds

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "project": self.project,
            "telegram_chat_id": self.telegram_chat_id,
            "telegram_thread_id": self.telegram_thread_id,
            "message_count": self.message_count,
            "tokens_used": self.tokens_used,
            "subprocess_pid": self.subprocess_pid,
            "last_activity": self.last_activity,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ChatSession":
        return cls(**d)
