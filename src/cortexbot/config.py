"""Configuration loading with env var expansion."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class TelegramConfig:
    bot_token: str
    group_id: int


@dataclass
class ProjectConfig:
    path: Path
    mcp_config: str = ".mcp.json"
    default_branch: str = "main"


@dataclass
class DefaultsConfig:
    autonomy: str = "supervised"
    budget_usd: float = 10.0
    phase_budgets: dict[str, float] = field(default_factory=dict)
    session_rotation: dict[str, int] = field(default_factory=dict)
    timeouts: dict[str, int] = field(default_factory=dict)


@dataclass
class LoggingConfig:
    invocation_logs: bool = True
    retention_days: int = 30


@dataclass
class ClaudeConfig:
    binary: str = "claude"


@dataclass
class BotConfig:
    telegram: TelegramConfig
    projects: dict[str, ProjectConfig]
    defaults: DefaultsConfig
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    claude: ClaudeConfig = field(default_factory=ClaudeConfig)


def _expand_env_vars(value: str) -> str:
    """Replace ${VAR} with environment variable value. Raises on unset vars."""

    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        val = os.environ.get(var_name)
        if val is None:
            raise ValueError(
                f"Environment variable '{var_name}' is not set "
                f"(referenced as '${{{var_name}}}' in config)"
            )
        return val

    return re.sub(r"\$\{([^}]+)\}", replacer, value)


def _expand_recursive(data: Any) -> Any:
    """Recursively expand env vars in all string values."""
    if isinstance(data, str):
        return _expand_env_vars(data)
    if isinstance(data, dict):
        return {k: _expand_recursive(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_expand_recursive(item) for item in data]
    return data


def load_config(path: Path) -> BotConfig:
    """Load and validate config from YAML file.

    Args:
        path: Path to config.yaml

    Returns:
        Validated BotConfig

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If env vars are unset
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    expanded = _expand_recursive(raw)

    # Parse telegram
    tg = expanded["telegram"]
    telegram = TelegramConfig(bot_token=tg["bot_token"], group_id=tg["group_id"])

    # Parse projects
    projects = {}
    for name, proj in expanded.get("projects", {}).items():
        projects[name] = ProjectConfig(
            path=Path(proj["path"]),
            mcp_config=proj.get("mcp_config", ".mcp.json"),
            default_branch=proj.get("default_branch", "main"),
        )

    # Parse defaults
    defaults_raw = expanded.get("defaults", {})
    defaults = DefaultsConfig(
        autonomy=defaults_raw.get("autonomy", "supervised"),
        budget_usd=float(defaults_raw.get("budget_usd", 10.0)),
        phase_budgets=defaults_raw.get("phase_budgets", {}),
        session_rotation=defaults_raw.get("session_rotation", {}),
        timeouts=defaults_raw.get("timeouts", {}),
    )

    # Parse logging
    log_raw = expanded.get("logging", {})
    logging_config = LoggingConfig(
        invocation_logs=log_raw.get("invocation_logs", True),
        retention_days=int(log_raw.get("retention_days", 30)),
    )

    # Parse claude
    claude_raw = expanded.get("claude", {})
    claude = ClaudeConfig(binary=claude_raw.get("binary", "claude"))

    return BotConfig(
        telegram=telegram,
        projects=projects,
        defaults=defaults,
        logging=logging_config,
        claude=claude,
    )
