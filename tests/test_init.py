import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from cortexbot.cli.init import (
    run_init, validate_token_format, check_claude_binary, check_superpowers,
)


def test_validate_token_format_valid():
    """Valid bot token format passes."""
    assert validate_token_format("123456789:ABCdefGHIjklMNOpqrsTUVwxyz_0123456") is True


def test_validate_token_format_invalid():
    """Invalid token format fails."""
    assert validate_token_format("not-a-token") is False
    assert validate_token_format("") is False


def test_check_claude_binary_found():
    """Returns True when claude binary is accessible."""
    with patch("shutil.which", return_value="/usr/bin/claude"):
        assert check_claude_binary("claude") is True


def test_check_claude_binary_not_found():
    """Returns False when claude binary is not found."""
    with patch("shutil.which", return_value=None):
        assert check_claude_binary("claude") is False


def test_check_superpowers_installed():
    """Returns True when superpowers plugin responds."""
    with patch("cortexbot.cli.init.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="brainstorming skill superpowers")
        assert check_superpowers() is True


def test_check_superpowers_not_installed():
    """Returns False when superpowers plugin probe fails."""
    with patch("cortexbot.cli.init.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="unknown skill")
        assert check_superpowers() is False


def test_run_init_creates_directory_structure(tmp_path):
    """Init creates ~/.cortexbot/ with config.yaml, .env, tasks/, chats/, logs/."""
    bot_dir = tmp_path / ".cortexbot"

    with patch("builtins.input", side_effect=["123456789:ABCdefGHIjklMNOpqrsTUVwxyz_0123456"]), \
         patch("cortexbot.cli.init.shutil.which", return_value="/usr/bin/claude"), \
         patch("cortexbot.cli.init.subprocess.run") as mock_run:
        # Claude --version and superpowers check both succeed
        mock_run.return_value = MagicMock(returncode=0, stdout="claude 1.0.0")
        run_init(bot_dir)

    assert (bot_dir / "config.yaml").exists()
    assert (bot_dir / ".env").exists()
    assert (bot_dir / "tasks").is_dir()
    assert (bot_dir / "chats").is_dir()
    assert (bot_dir / "logs").is_dir()

    # .env contains token
    env_content = (bot_dir / ".env").read_text()
    assert "CORTEXBOT_TELEGRAM_TOKEN=" in env_content
