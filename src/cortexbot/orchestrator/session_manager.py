"""Claude Code subprocess lifecycle and global mutex.

One task runs at a time globally (V1). The mutex prevents concurrent
Claude Code invocations.
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

    @property
    def is_busy(self) -> bool:
        """Whether the mutex is currently held."""
        return self._lock.locked()

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

    async def acquire(self) -> None:
        """Acquire the global mutex. Blocks until available."""
        await self._lock.acquire()

    def release(self) -> None:
        """Release the global mutex."""
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
