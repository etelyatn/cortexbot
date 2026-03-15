"""Tests for session manager (mutex, subprocess lifecycle)."""

import asyncio

import pytest

from cortexbot.orchestrator.session_manager import SessionManager


@pytest.mark.asyncio
class TestSessionManager:
    """Test global mutex and session tracking."""

    async def test_acquire_and_release(self) -> None:
        """Can acquire and release the global mutex."""
        mgr = SessionManager()
        assert not mgr.is_busy
        await mgr.acquire()
        assert mgr.is_busy
        mgr.release()
        assert not mgr.is_busy

    async def test_acquire_blocks_second_caller(self) -> None:
        """Second acquire blocks until first releases."""
        mgr = SessionManager()
        await mgr.acquire()

        acquired = False

        async def second_acquire():
            nonlocal acquired
            await mgr.acquire()
            acquired = True
            mgr.release()

        task = asyncio.create_task(second_acquire())
        await asyncio.sleep(0.05)
        assert not acquired  # still blocked

        mgr.release()
        await asyncio.sleep(0.05)
        assert acquired  # now unblocked

        await task

    async def test_track_pid(self) -> None:
        """Can set and clear subprocess PID."""
        mgr = SessionManager()
        assert mgr.current_pid is None
        mgr.current_pid = 12345
        assert mgr.current_pid == 12345
        mgr.current_pid = None
        assert mgr.current_pid is None

    async def test_cancel_flag(self) -> None:
        """Cancel flag can be set without acquiring mutex."""
        mgr = SessionManager()
        assert not mgr.cancel_requested
        mgr.request_cancel()
        assert mgr.cancel_requested
        mgr.clear_cancel()
        assert not mgr.cancel_requested

    async def test_kill_subprocess_no_process(self) -> None:
        """Kill with no PID returns False."""
        mgr = SessionManager()
        assert mgr.kill_subprocess() is False

    async def test_kill_subprocess_dead_pid(self) -> None:
        """Kill with non-existent PID returns False and clears PID."""
        mgr = SessionManager()
        mgr.current_pid = 999999999  # non-existent
        result = mgr.kill_subprocess()
        assert result is False
        assert mgr.current_pid is None
