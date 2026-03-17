"""V2 configuration — YAML + env var expansion + project management."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


def _expand_env_vars(value):
    """Recursively expand ${VAR} patterns in strings using os.environ."""
    if isinstance(value, str):
        return re.sub(
            r"\$\{(\w+)\}",
            lambda m: os.environ.get(m.group(1), m.group(0)),
            value,
        )
    if isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(v) for v in value]
    return value


@dataclass
class TelegramConfig:
    bot_token: str = ""


@dataclass
class ProjectConfig:
    path: str = ""
    mcp_config: str = ".mcp.json"
    default_branch: str = "main"
    group_id: int = 0


@dataclass
class DefaultsConfig:
    token_budget: int = 500_000
    timeouts: dict = field(default_factory=lambda: {"default": 900})
    session_rotation: dict = field(default_factory=lambda: {"execute": 100})
    max_cycles: int = 3
    chat_inactivity_timeout: int = 7200


@dataclass
class LoggingConfig:
    invocation_logs: bool = True
    retention_days: int = 30


@dataclass
class BotConfig:
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    projects: dict = field(default_factory=dict)  # name -> ProjectConfig
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    claude_binary: str = "claude"


def load_config(config_path: Path) -> BotConfig:
    """Load config from YAML file with env var expansion."""
    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    raw = _expand_env_vars(raw)

    telegram_raw = raw.get("telegram", {})
    telegram = TelegramConfig(bot_token=telegram_raw.get("bot_token", ""))

    projects = {}
    for name, proj_raw in raw.get("projects", {}).items():
        projects[name] = ProjectConfig(
            path=proj_raw.get("path", ""),
            mcp_config=proj_raw.get("mcp_config", ".mcp.json"),
            default_branch=proj_raw.get("default_branch", "main"),
            group_id=proj_raw.get("group_id", 0),
        )

    defaults_raw = raw.get("defaults", {})
    chat_raw = defaults_raw.get("chat", {})
    defaults = DefaultsConfig(
        token_budget=defaults_raw.get("token_budget", 500_000),
        timeouts=defaults_raw.get("timeouts", {"default": 900}),
        session_rotation=defaults_raw.get("session_rotation", {"execute": 100}),
        max_cycles=defaults_raw.get("max_cycles", 3),
        chat_inactivity_timeout=chat_raw.get("inactivity_timeout", 7200),
    )

    logging_raw = raw.get("logging", {})
    logging_config = LoggingConfig(
        invocation_logs=logging_raw.get("invocation_logs", True),
        retention_days=logging_raw.get("retention_days", 30),
    )

    claude_raw = raw.get("claude", {})

    return BotConfig(
        telegram=telegram,
        projects=projects,
        defaults=defaults,
        logging=logging_config,
        claude_binary=claude_raw.get("binary", "claude"),
    )


def add_project(config_path: Path, name: str, path: str, group_id: int) -> None:
    """Add a project entry to the config YAML file."""
    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    if "projects" not in raw:
        raw["projects"] = {}

    raw["projects"][name] = {
        "path": path,
        "mcp_config": ".mcp.json",
        "default_branch": "main",
        "group_id": group_id,
    }

    with open(config_path, "w") as f:
        yaml.dump(raw, f, default_flow_style=False)
