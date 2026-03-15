"""Shared test fixtures for CortexBot."""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test data."""
    return tmp_path


@pytest.fixture
def sample_config_yaml(tmp_dir: Path) -> Path:
    """Write a minimal config.yaml and return its path."""
    config = tmp_dir / "config.yaml"
    config.write_text(
        """\
telegram:
  bot_token: "${TEST_BOT_TOKEN}"
  group_id: -1001234567890

projects:
  sandbox:
    path: "D:/UnrealProjects/CortexSandbox"
    mcp_config: ".mcp.json"
    default_branch: "main"

defaults:
  autonomy: "supervised"
  budget_usd: 10.00
  phase_budgets:
    design: 3.00
    plan: 2.00
    implement: 5.00
    test: 3.00
    merge: 1.00
  session_rotation:
    design: 50
    plan: 50
    implement: 100
    test: 40
  timeouts:
    implement: 1800
    default: 900

logging:
  invocation_logs: true
  retention_days: 30

claude:
  binary: "claude"
"""
    )
    return config
