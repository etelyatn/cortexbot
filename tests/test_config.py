import os
import pytest
import yaml
from pathlib import Path
from cortexbot.config import load_config, BotConfig, ProjectConfig


def test_load_v2_config(tmp_path):
    """V2 config has token_budget (not budget_usd), chat section, no autonomy."""
    config_yaml = tmp_path / "config.yaml"
    config_yaml.write_text(yaml.dump({
        "telegram": {"bot_token": "test-token"},
        "projects": {
            "sandbox": {
                "path": "D:/UnrealProjects/CortexSandbox",
                "mcp_config": ".mcp.json",
                "default_branch": "main",
                "group_id": -1001234567890,
            }
        },
        "defaults": {
            "token_budget": 500000,
            "timeouts": {
                "brainstorm": 900,
                "plan": 900,
                "execute": 1800,
                "review": 900,
                "chat": 600,
                "default": 900,
            },
            "session_rotation": {"execute": 100},
            "max_cycles": 3,
            "chat": {"inactivity_timeout": 7200},
        },
        "logging": {"invocation_logs": True, "retention_days": 30},
        "claude": {"binary": "claude"},
    }))

    config = load_config(config_yaml)

    assert config.telegram.bot_token == "test-token"
    assert config.projects["sandbox"].group_id == -1001234567890
    assert config.defaults.token_budget == 500000
    assert config.defaults.timeouts["chat"] == 600
    assert config.defaults.max_cycles == 3
    assert config.defaults.chat_inactivity_timeout == 7200
    assert config.claude_binary == "claude"


def test_env_var_expansion(tmp_path, monkeypatch):
    """${VAR} syntax expands from environment."""
    monkeypatch.setenv("CORTEXBOT_TELEGRAM_TOKEN", "secret-token-123")
    config_yaml = tmp_path / "config.yaml"
    config_yaml.write_text(yaml.dump({
        "telegram": {"bot_token": "${CORTEXBOT_TELEGRAM_TOKEN}"},
        "projects": {},
        "defaults": {
            "token_budget": 500000,
            "timeouts": {"default": 900},
            "max_cycles": 3,
        },
    }))

    config = load_config(config_yaml)
    assert config.telegram.bot_token == "secret-token-123"


def test_project_has_group_id(tmp_path):
    """V2 projects include group_id captured from /project-add."""
    config_yaml = tmp_path / "config.yaml"
    config_yaml.write_text(yaml.dump({
        "telegram": {"bot_token": "test"},
        "projects": {
            "sandbox": {
                "path": "/some/path",
                "mcp_config": ".mcp.json",
                "default_branch": "main",
                "group_id": -100999,
            }
        },
        "defaults": {"token_budget": 500000, "timeouts": {"default": 900}, "max_cycles": 3},
    }))

    config = load_config(config_yaml)
    assert config.projects["sandbox"].group_id == -100999


def test_add_project(tmp_path):
    """Adding a project appends to config YAML and reloads."""
    config_yaml = tmp_path / "config.yaml"
    config_yaml.write_text(yaml.dump({
        "telegram": {"bot_token": "test"},
        "projects": {},
        "defaults": {"token_budget": 500000, "timeouts": {"default": 900}, "max_cycles": 3},
    }))

    config = load_config(config_yaml)
    from cortexbot.config import add_project
    add_project(
        config_path=config_yaml,
        name="newproject",
        path="/new/path",
        group_id=-100555,
    )

    # Reload and verify
    config2 = load_config(config_yaml)
    assert "newproject" in config2.projects
    assert config2.projects["newproject"].path == "/new/path"
    assert config2.projects["newproject"].group_id == -100555
