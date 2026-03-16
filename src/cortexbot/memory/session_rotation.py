"""Session rotation — detect threshold and bridge context."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

DEFAULT_ROTATION_THRESHOLD = 50


def should_rotate(
    phase: str,
    event_count: int,
    thresholds: dict[str, int],
) -> bool:
    """Check if the session should be rotated.

    Args:
        phase: Current phase name
        event_count: Number of countable events in current session
        thresholds: Phase-specific thresholds from config

    Returns:
        True if rotation threshold reached
    """
    threshold = thresholds.get(phase, DEFAULT_ROTATION_THRESHOLD)
    return event_count >= threshold
