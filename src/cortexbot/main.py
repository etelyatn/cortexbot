"""CortexBot entry point."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from cortexbot.config import load_config
from cortexbot.events.bus import EventBus
from cortexbot.bot.telegram import create_application

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path.home() / ".cortexbot" / "config.yaml"


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
