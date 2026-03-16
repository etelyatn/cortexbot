"""Tests for session rotation logic."""

import pytest

from cortexbot.memory.session_rotation import should_rotate


class TestShouldRotate:
    """Test session rotation threshold checks."""

    def test_below_threshold_no_rotate(self) -> None:
        assert should_rotate("design", event_count=30, thresholds={"design": 50}) is False

    def test_at_threshold_rotates(self) -> None:
        assert should_rotate("design", event_count=50, thresholds={"design": 50}) is True

    def test_above_threshold_rotates(self) -> None:
        assert should_rotate("implement", event_count=120, thresholds={"implement": 100}) is True

    def test_missing_threshold_uses_default(self) -> None:
        """Phases without explicit threshold use 50 as default."""
        assert should_rotate("unknown_phase", event_count=60, thresholds={}) is True

    def test_zero_events_no_rotate(self) -> None:
        assert should_rotate("design", event_count=0, thresholds={"design": 50}) is False
