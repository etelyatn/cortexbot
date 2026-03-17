"""Shared test fixtures for CortexBot."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test data."""
    return tmp_path


@pytest.fixture
def sample_config_yaml(tmp_dir: Path) -> Path:
    """Write a minimal V2 config.yaml and return its path."""
    config = tmp_dir / "config.yaml"
    config.write_text(
        """\
telegram:
  bot_token: "${TEST_BOT_TOKEN}"

projects:
  sandbox:
    path: "D:/UnrealProjects/CortexSandbox"
    mcp_config: ".mcp.json"
    default_branch: "main"
    group_id: -1001234567890

defaults:
  token_budget: 500000
  timeouts:
    brainstorm: 900
    plan: 900
    execute: 1800
    review: 900
    chat: 600
    default: 900
  session_rotation:
    execute: 100
  max_cycles: 3
  chat:
    inactivity_timeout: 7200

logging:
  invocation_logs: true
  retention_days: 30

claude:
  binary: "claude"
"""
    )
    return config
