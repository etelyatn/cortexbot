"""CortexBot V2 entry point."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import psutil
from dotenv import load_dotenv

from cortexbot.config import load_config
from cortexbot.memory.store import TaskStore
from cortexbot.chat.store import ChatSessionStore
from cortexbot.orchestrator.task_manager import TaskState
from cortexbot.orchestrator.session_manager import SessionManager
from cortexbot.events.bus import EventBus
from cortexbot.events.telegram_handler import TelegramEventHandler
from cortexbot.bot.telegram import create_application
from cortexbot.bot.commands import init_commands

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path.home() / ".cortexbot" / "config.yaml"


async def recover_interrupted_tasks(store: TaskStore) -> list[TaskState]:
    """Detect and clean up tasks with dead subprocess PIDs."""
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

    # Load .env
    bot_dir = Path.home() / ".cortexbot"
    env_path = bot_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        print("Config not found. Run `cortexbot init` first.")
        sys.exit(1)

    logger.info("Loading config from %s", path)
    config = load_config(path)

    # Initialize components
    store = TaskStore(base_dir=bot_dir)
    chat_store = ChatSessionStore(base_dir=bot_dir)
    event_bus = EventBus()
    session_mgr = SessionManager()

    # Wire commands
    init_commands(config, store, session_mgr, event_bus, chat_store=chat_store)

    # Crash recovery
    interrupted = await recover_interrupted_tasks(store)
    if interrupted:
        logger.info("Recovered %d interrupted task(s)", len(interrupted))

    # Clean up expired chats
    for session in chat_store.list_sessions():
        if session.is_expired(config.defaults.chat_inactivity_timeout):
            chat_store.delete(session.session_id)
            logger.info("Cleaned up expired chat session %s", session.session_id)

    # Build Telegram app
    app = create_application(config, event_bus, store, session_mgr)

    # Wire event handler
    handler = TelegramEventHandler(app.bot, event_bus)

    # Shutdown event
    shutdown_event = asyncio.Event()

    def request_shutdown() -> None:
        logger.info("Shutdown requested")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGINT, request_shutdown)
        loop.add_signal_handler(signal.SIGTERM, request_shutdown)

    logger.info("CortexBot V2 starting polling...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(
        allowed_updates=["message"],
        drop_pending_updates=True,
    )

    try:
        await shutdown_event.wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        logger.info("CortexBot shutting down...")

        if session_mgr.current_pid:
            session_mgr.kill_subprocess()

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
