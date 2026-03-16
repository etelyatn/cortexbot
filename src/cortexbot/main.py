"""CortexBot entry point."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import psutil

from cortexbot.config import load_config
from cortexbot.events.bus import EventBus
from cortexbot.bot.telegram import create_application
from cortexbot.events.telegram_handler import TelegramEventHandler
from cortexbot.memory.store import TaskStore
from cortexbot.orchestrator.task_manager import TaskState
from cortexbot.orchestrator.session_manager import SessionManager

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path.home() / ".cortexbot" / "config.yaml"


async def recover_interrupted_tasks(store: TaskStore) -> list[TaskState]:
    """Detect and mark interrupted tasks from a previous crash.

    Scans all tasks for in_progress status with dead subprocess PIDs.

    Returns:
        List of tasks that were interrupted
    """
    interrupted = []

    for task in store.list_tasks():
        if task.current_phase_status != "in_progress":
            continue

        pid_alive = False
        if task.subprocess_pid is not None:
            try:
                proc = psutil.Process(task.subprocess_pid)
                pid_alive = proc.is_running()
            except psutil.NoSuchProcess:
                pid_alive = False

        if not pid_alive:
            task.current_phase_status = "interrupted"
            task.subprocess_pid = None
            task.updated_at = datetime.now(timezone.utc).isoformat()
            store.save_task(task)
            interrupted.append(task)
            logger.warning(
                "Task %d (%s) was interrupted — phase '%s' marked interrupted",
                task.thread_id,
                task.title,
                task.current_phase,
            )

    return interrupted


async def run(config_path: Path | None = None) -> None:
    """Start CortexBot."""
    import signal

    path = config_path or DEFAULT_CONFIG_PATH
    logger.info("Loading config from %s", path)
    config = load_config(path)

    # Initialize components
    base_dir = Path.home() / ".cortexbot"
    store = TaskStore(base_dir=base_dir)
    event_bus = EventBus()
    session_mgr = SessionManager()

    # Crash recovery
    interrupted = await recover_interrupted_tasks(store)
    for task in interrupted:
        logger.warning(
            "Task %d (%s) was interrupted in phase '%s'",
            task.thread_id,
            task.title,
            task.current_phase,
        )

    # Build Telegram app
    app = create_application(config, event_bus)
    app.bot_data["store"] = store
    app.bot_data["session_manager"] = session_mgr

    # Wire event handler so phase/task events are posted to Telegram
    telegram_handler = TelegramEventHandler(app.bot, event_bus)

    # Shutdown event
    shutdown_event = asyncio.Event()

    def request_shutdown() -> None:
        logger.info("Shutdown requested")
        shutdown_event.set()

    # Register signal handlers
    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGINT, request_shutdown)
        loop.add_signal_handler(signal.SIGTERM, request_shutdown)

    logger.info("CortexBot starting polling...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(
        allowed_updates=["message"],
        drop_pending_updates=True,
    )

    # Wait for shutdown signal
    try:
        await shutdown_event.wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        logger.info("CortexBot shutting down...")

        # Kill any running subprocess
        if session_mgr.current_pid:
            session_mgr.kill_subprocess()

        # Save all task states
        for task in store.list_tasks():
            if task.current_phase_status == "in_progress":
                task.current_phase_status = "interrupted"
                store.save_task(task)

        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        logger.info("CortexBot stopped.")


def main() -> None:
    """Entry point for cortexbot console script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    config_path = None
    if len(sys.argv) > 1:
        config_path = Path(sys.argv[1])

    asyncio.run(run(config_path))


if __name__ == "__main__":
    main()
