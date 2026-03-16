"""Autonomy profiles and escalation logic."""

from __future__ import annotations

import enum
import logging

logger = logging.getLogger(__name__)


class AutonomyDecision(enum.Enum):
    """Decision outcome for autonomy logic."""

    RETRY = "retry"
    ESCALATE = "escalate"
    ADVANCE = "advance"
    WAIT_FOR_USER = "wait_for_user"


def should_auto_advance(autonomy: str) -> bool:
    """Whether the bot should automatically advance to the next phase."""
    return autonomy == "autonomous"


def decide_on_error(
    autonomy: str,
    retry_count: int,
    same_error: bool,
) -> AutonomyDecision:
    """Decide what to do when a phase errors."""
    if autonomy == "supervised":
        if retry_count < 1:
            return AutonomyDecision.RETRY
        return AutonomyDecision.ESCALATE

    # Autonomous
    if retry_count >= 3:
        return AutonomyDecision.ESCALATE

    # Same error on 2nd+ consecutive retry → escalate immediately
    if same_error and retry_count >= 1:
        return AutonomyDecision.ESCALATE

    return AutonomyDecision.RETRY


def decide_on_phase_complete(
    autonomy: str,
    gate_passed: bool,
) -> AutonomyDecision:
    """Decide what to do when a phase completes."""
    if autonomy == "supervised":
        return AutonomyDecision.WAIT_FOR_USER

    # Autonomous
    if gate_passed:
        return AutonomyDecision.ADVANCE
    return AutonomyDecision.RETRY
