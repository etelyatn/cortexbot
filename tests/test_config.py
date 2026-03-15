"""Tests for config loading."""

import os
from pathlib import Path

import pytest

from cortexbot.config import BotConfig, load_config


class TestLoadConfig:
    """Test YAML config loading with env var expansion."""

    def test_load_basic_config(self, sample_config_yaml: Path) -> None:
        """Config loads all sections from valid YAML."""
        os.environ["TEST_BOT_TOKEN"] = "fake-token-123"
        try:
            config = load_config(sample_config_yaml)
            assert config.telegram.bot_token == "fake-token-123"
            assert config.telegram.group_id == -1001234567890
            assert "sandbox" in config.projects
            assert config.projects["sandbox"].path == Path("D:/UnrealProjects/CortexSandbox")
            assert config.defaults.autonomy == "supervised"
            assert config.defaults.budget_usd == 10.00
        finally:
            del os.environ["TEST_BOT_TOKEN"]

    def test_env_var_expansion(self, tmp_dir: Path) -> None:
        """${VAR} in YAML values is replaced with env var."""
        config_file = tmp_dir / "config.yaml"
        config_file.write_text(
            """\
telegram:
  bot_token: "${MY_SECRET_TOKEN}"
  group_id: -100

projects:
  test:
    path: "C:/test"
    mcp_config: ".mcp.json"
    default_branch: "main"

defaults:
  autonomy: "supervised"
  budget_usd: 5.00
"""
        )
        os.environ["MY_SECRET_TOKEN"] = "expanded-secret"
        try:
            config = load_config(config_file)
            assert config.telegram.bot_token == "expanded-secret"
        finally:
            del os.environ["MY_SECRET_TOKEN"]

    def test_missing_env_var_raises(self, tmp_dir: Path) -> None:
        """Unset env var reference raises clear error."""
        config_file = tmp_dir / "config.yaml"
        config_file.write_text(
            """\
telegram:
  bot_token: "${NONEXISTENT_VAR_12345}"
  group_id: -100

projects:
  test:
    path: "C:/test"
    mcp_config: ".mcp.json"
    default_branch: "main"

defaults:
  autonomy: "supervised"
  budget_usd: 5.00
"""
        )
        with pytest.raises(ValueError, match="NONEXISTENT_VAR_12345"):
            load_config(config_file)

    def test_missing_file_raises(self, tmp_dir: Path) -> None:
        """Non-existent config file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config(tmp_dir / "nonexistent.yaml")

    def test_project_defaults(self, sample_config_yaml: Path) -> None:
        """Projects have correct default_branch and mcp_config."""
        os.environ["TEST_BOT_TOKEN"] = "fake"
        try:
            config = load_config(sample_config_yaml)
            project = config.projects["sandbox"]
            assert project.default_branch == "main"
            assert project.mcp_config == ".mcp.json"
        finally:
            del os.environ["TEST_BOT_TOKEN"]

    def test_phase_budgets(self, sample_config_yaml: Path) -> None:
        """Phase budgets are loaded from config."""
        os.environ["TEST_BOT_TOKEN"] = "fake"
        try:
            config = load_config(sample_config_yaml)
            assert config.defaults.phase_budgets["design"] == 3.00
            assert config.defaults.phase_budgets["implement"] == 5.00
        finally:
            del os.environ["TEST_BOT_TOKEN"]

    def test_timeout_defaults(self, sample_config_yaml: Path) -> None:
        """Timeouts loaded with implement override and default fallback."""
        os.environ["TEST_BOT_TOKEN"] = "fake"
        try:
            config = load_config(sample_config_yaml)
            assert config.defaults.timeouts["implement"] == 1800
            assert config.defaults.timeouts["default"] == 900
        finally:
            del os.environ["TEST_BOT_TOKEN"]

    def test_session_rotation_thresholds(self, sample_config_yaml: Path) -> None:
        """Session rotation thresholds loaded per phase."""
        os.environ["TEST_BOT_TOKEN"] = "fake"
        try:
            config = load_config(sample_config_yaml)
            assert config.defaults.session_rotation["design"] == 50
            assert config.defaults.session_rotation["implement"] == 100
        finally:
            del os.environ["TEST_BOT_TOKEN"]
