"""Tests for Telegram command parsing."""

import pytest

from cortexbot.bot.commands import parse_task_args, parse_skip_args


class TestParseTaskArgs:
    """Test /task command argument parsing."""

    def test_simple_title(self) -> None:
        """Parse a simple task title."""
        result = parse_task_args("Add data table support")
        assert result.title == "Add data table support"
        assert result.project is None
        assert result.autonomy is None

    def test_title_with_project(self) -> None:
        """Parse title with --project flag."""
        result = parse_task_args("Fix bug --project sandbox")
        assert result.title == "Fix bug"
        assert result.project == "sandbox"

    def test_title_with_autonomy(self) -> None:
        """Parse title with --autonomy flag."""
        result = parse_task_args("Big refactor --autonomy autonomous")
        assert result.title == "Big refactor"
        assert result.autonomy == "autonomous"

    def test_title_with_both_flags(self) -> None:
        """Parse title with both flags."""
        result = parse_task_args("New feature --project mirror --autonomy autonomous")
        assert result.title == "New feature"
        assert result.project == "mirror"
        assert result.autonomy == "autonomous"

    def test_empty_title_raises(self) -> None:
        """Empty title raises ValueError."""
        with pytest.raises(ValueError, match="Task title is required"):
            parse_task_args("")

    def test_only_flags_raises(self) -> None:
        """Only flags and no title raises ValueError."""
        with pytest.raises(ValueError, match="Task title is required"):
            parse_task_args("--project sandbox")


class TestParseSkipArgs:
    """Test /skip command argument parsing."""

    def test_no_args_skips_current(self) -> None:
        """No args means skip current phase only."""
        result = parse_skip_args("")
        assert result is None  # None means "skip current"

    def test_target_phase(self) -> None:
        """Specific phase target."""
        result = parse_skip_args("implement")
        assert result == "implement"

    def test_invalid_phase_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown phase"):
            parse_skip_args("nonexistent")
