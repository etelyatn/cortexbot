"""CortexBot entry point."""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run() -> None:
    """Start CortexBot."""
    logger.info("CortexBot starting...")


def main() -> None:
    """Entry point for cortexbot console script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
