"""Tests for autonomy profile decision logic."""

import pytest

from cortexbot.orchestrator.autonomy import (
    AutonomyDecision,
    decide_on_error,
    decide_on_phase_complete,
    should_auto_advance,
)


class TestShouldAutoAdvance:
    """Test whether bot should auto-advance to next phase."""

    def test_supervised_never_auto_advances(self) -> None:
        assert should_auto_advance("supervised") is False

    def test_autonomous_auto_advances(self) -> None:
        assert should_auto_advance("autonomous") is True


class TestDecideOnError:
    """Test error handling decisions per autonomy profile."""

    def test_supervised_first_error_retries(self) -> None:
        """Supervised: first error → retry."""
        result = decide_on_error("supervised", retry_count=0, same_error=False)
        assert result == AutonomyDecision.RETRY

    def test_supervised_second_error_escalates(self) -> None:
        """Supervised: second error → escalate."""
        result = decide_on_error("supervised", retry_count=1, same_error=False)
        assert result == AutonomyDecision.ESCALATE

    def test_autonomous_retries_up_to_3(self) -> None:
        """Autonomous: retry up to 3 times."""
        assert decide_on_error("autonomous", retry_count=0, same_error=False) == AutonomyDecision.RETRY
        assert decide_on_error("autonomous", retry_count=1, same_error=False) == AutonomyDecision.RETRY
        assert decide_on_error("autonomous", retry_count=2, same_error=False) == AutonomyDecision.RETRY

    def test_autonomous_exhausted_retries_escalates(self) -> None:
        """Autonomous: 3rd retry exhausted → escalate."""
        result = decide_on_error("autonomous", retry_count=3, same_error=False)
        assert result == AutonomyDecision.ESCALATE

    def test_autonomous_same_error_twice_escalates(self) -> None:
        """Autonomous: same error on 2nd consecutive retry → escalate immediately."""
        result = decide_on_error("autonomous", retry_count=1, same_error=True)
        assert result == AutonomyDecision.ESCALATE

    def test_autonomous_same_error_first_time_retries(self) -> None:
        """Autonomous: first occurrence of error → retry even if same_error flag."""
        result = decide_on_error("autonomous", retry_count=0, same_error=True)
        assert result == AutonomyDecision.RETRY


class TestDecideOnPhaseComplete:
    """Test phase completion decisions."""

    def test_supervised_waits(self) -> None:
        """Supervised: wait for user /continue."""
        result = decide_on_phase_complete("supervised", gate_passed=True)
        assert result == AutonomyDecision.WAIT_FOR_USER

    def test_autonomous_gate_passed_advances(self) -> None:
        """Autonomous with gate passed: advance."""
        result = decide_on_phase_complete("autonomous", gate_passed=True)
        assert result == AutonomyDecision.ADVANCE

    def test_autonomous_gate_failed_retries(self) -> None:
        """Autonomous with gate failed: retry the phase."""
        result = decide_on_phase_complete("autonomous", gate_passed=False)
        assert result == AutonomyDecision.RETRY
