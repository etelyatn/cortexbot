"""CortexBot entry point."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import psutil
from dotenv import load_dotenv

from cortexbot.config import load_config
from cortexbot.events.bus import EventBus
from cortexbot.bot.telegram import create_application
from cortexbot.memory.store import TaskStore
from cortexbot.orchestrator.task_manager import TaskState
from cortexbot.orchestrator.session_manager import SessionManager

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path.home() / ".cortexbot" / "config.yaml"


async def recover_interrupted_tasks(store: TaskStore) -> list[TaskState]:
    """Detect and clean up tasks with dead subprocess PIDs.

    Scans all active tasks for dead subprocess PIDs. Clears PID and session
    so the task can be resumed from its last artifact.

    Returns:
        List of tasks that had dead PIDs cleared
    """
    interrupted = []

    for task in store.list_tasks():
        if task.status != "active" or task.subprocess_pid is None:
            continue

        pid_alive = False
        try:
            proc = psutil.Process(task.subprocess_pid)
            pid_alive = proc.is_running()
        except psutil.NoSuchProcess:
            pid_alive = False

        if not pid_alive:
            task.subprocess_pid = None
            task.session_id = None
            task.last_error = "Process died — will resume from last artifact"
            task.updated_at = datetime.now(timezone.utc).isoformat()
            store.save_task(task)
            interrupted.append(task)
            logger.warning(
                "Task %s (%s) — dead PID cleared, will resume at '%s'",
                task.task_id,
                task.description[:50],
                task.next_action,
            )

    return interrupted


async def run(config_path: Path | None = None) -> None:
    """Start CortexBot."""
    import signal

    # Load .env from bot directory
    bot_dir = Path.home() / ".cortexbot"
    env_path = bot_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    path = config_path or DEFAULT_CONFIG_PATH
    logger.info("Loading config from %s", path)
    config = load_config(path)

    # Initialize components
    store = TaskStore(base_dir=bot_dir)
    event_bus = EventBus()
    session_mgr = SessionManager()

    # Crash recovery
    interrupted = await recover_interrupted_tasks(store)
    for task in interrupted:
        logger.warning(
            "Task %s (%s) — will resume at '%s'",
            task.task_id,
            task.description[:50],
            task.next_action,
        )

    # Build Telegram app
    app = create_application(config, event_bus)
    app.bot_data["store"] = store
    app.bot_data["session_manager"] = session_mgr

    # V2: TelegramEventHandler wiring deferred to Task 16
    # telegram_handler = TelegramEventHandler(
    #     app.bot, event_bus, group_chat_id=config.telegram.group_id,
    # )

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

        # Save interrupted tasks on shutdown
        for task in store.list_tasks():
            if task.status == "active" and task.subprocess_pid is not None:
                task.subprocess_pid = None
                task.session_id = None
                task.last_error = "Bot shutdown"
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

    if len(sys.argv) > 1 and sys.argv[1] == "init":
        from cortexbot.cli.init import run_init
        bot_dir = Path.home() / ".cortexbot"
        run_init(bot_dir)
        return

    config_path = None
    if len(sys.argv) > 1:
        config_path = Path(sys.argv[1])

    asyncio.run(run(config_path))


if __name__ == "__main__":
    main()
