"""Claude Code subprocess lifecycle and global mutex.

One subprocess at a time. Tasks and chats are mutually exclusive.
"""

from __future__ import annotations

import asyncio
import logging

import psutil

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages Claude Code subprocess lifecycle with global mutex."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._current_pid: int | None = None
        self._cancel_requested = False
        self.active_type: str | None = None  # "task" | "chat"

    @property
    def is_busy(self) -> bool:
        """Whether a subprocess is active."""
        return self.active_type is not None

    @property
    def current_pid(self) -> int | None:
        """PID of the running Claude Code subprocess, if any."""
        return self._current_pid

    @current_pid.setter
    def current_pid(self, pid: int | None) -> None:
        self._current_pid = pid

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_requested

    def request_cancel(self) -> None:
        """Set cancellation flag (does NOT acquire mutex)."""
        self._cancel_requested = True

    def clear_cancel(self) -> None:
        """Clear cancellation flag."""
        self._cancel_requested = False

    async def acquire(self, subprocess_type: str = "task") -> None:
        """Acquire the global mutex. Blocks until available."""
        await self._lock.acquire()
        self.active_type = subprocess_type
        self._cancel_requested = False

    async def try_acquire(self, subprocess_type: str = "task") -> None:
        """Try to acquire — raises RuntimeError if busy."""
        if self.is_busy:
            raise RuntimeError(
                f"A {self.active_type} is running. "
                f"{'Use /cancel or wait.' if self.active_type == 'task' else 'Wait for response.'}"
            )
        await self.acquire(subprocess_type)

    def release(self) -> None:
        """Release the global mutex and clear state."""
        self.active_type = None
        self._current_pid = None
        self._cancel_requested = False
        try:
            self._lock.release()
        except RuntimeError:
            logger.warning("Attempted to release unlocked mutex")

    def kill_subprocess(self) -> bool:
        """Kill the current subprocess and its process tree.

        Returns:
            True if a process was killed, False if nothing was running
        """
        pid = self._current_pid
        if pid is None:
            return False

        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            parent.kill()
            logger.info("Killed subprocess tree (PID %d, %d children)", pid, len(children))
            return True
        except psutil.NoSuchProcess:
            logger.info("Subprocess PID %d already gone", pid)
            return False
        finally:
            self._current_pid = None
