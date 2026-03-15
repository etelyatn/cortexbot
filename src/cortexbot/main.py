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
from cortexbot.memory.store import TaskStore
from cortexbot.orchestrator.task_manager import TaskState

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
    """Start CortexBot.

    Args:
        config_path: Override path to config.yaml. Defaults to ~/.cortexbot/config.yaml
    """
    path = config_path or DEFAULT_CONFIG_PATH
    logger.info("Loading config from %s", path)
    config = load_config(path)

    event_bus = EventBus()
    app = create_application(config, event_bus)

    logger.info("CortexBot starting polling...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(
        allowed_updates=["message"],
        drop_pending_updates=True,
    )

    # Run until stopped
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("CortexBot shutting down...")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


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
