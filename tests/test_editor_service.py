"""Tests for editor lifecycle management in unreal service."""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path
from cortexbot.services.unreal import check_editor_status, start_editor


@pytest.mark.asyncio
async def test_check_editor_status_running(tmp_path):
    """Status reports running when port file exists and TCP responds."""
    # Create fake port file
    saved = tmp_path / "Saved"
    saved.mkdir()
    (saved / "CortexPort-12345.txt").write_text("8742")

    # Create fake .uproject
    (tmp_path / "Test.uproject").write_text("{}")

    mock_conn = MagicMock()
    mock_conn.send_command.return_value = {"data": {"subsystems": {"data": {}, "blueprint": {}}}}

    with patch("cortexbot.services.unreal._make_connection", return_value=mock_conn), \
         patch("cortexbot.services.unreal._tcp_probe", return_value=True), \
         patch.dict("os.environ", {"UE_56_PATH": "C:/UE"}), \
         patch("os.path.isdir", return_value=True):
        result = await check_editor_status(str(tmp_path))

    assert result["running"] is True
    assert result["port"] == 8742
    assert result["pid"] == 12345
    assert "data" in result["domains"]
    assert "blueprint" in result["domains"]


@pytest.mark.asyncio
async def test_check_editor_status_not_running(tmp_path):
    """Status reports not running when no port file."""
    saved = tmp_path / "Saved"
    saved.mkdir()
    (tmp_path / "Test.uproject").write_text("{}")

    with patch.dict("os.environ", {"UE_56_PATH": "C:/UE"}), \
         patch("os.path.isdir", return_value=True):
        result = await check_editor_status(str(tmp_path))

    assert result["running"] is False
    assert result["can_start"] is True


@pytest.mark.asyncio
async def test_check_editor_status_no_engine_path(tmp_path):
    """Cannot start if UE_56_PATH not set."""
    saved = tmp_path / "Saved"
    saved.mkdir()
    (tmp_path / "Test.uproject").write_text("{}")

    with patch.dict("os.environ", {}, clear=True):
        result = await check_editor_status(str(tmp_path))

    assert result["running"] is False
    assert result["can_start"] is False
    assert result["engine_path"] is None


@pytest.mark.asyncio
async def test_check_editor_status_json_port_file(tmp_path):
    """Handles JSON-format port files."""
    saved = tmp_path / "Saved"
    saved.mkdir()
    (saved / "CortexPort-99.txt").write_text('{"port": 9000, "pid": 99}')
    (tmp_path / "Test.uproject").write_text("{}")

    mock_conn = MagicMock()
    mock_conn.send_command.return_value = {"data": {"subsystems": {"data": {}}}}

    with patch("cortexbot.services.unreal._make_connection", return_value=mock_conn), \
         patch("cortexbot.services.unreal._tcp_probe", return_value=True), \
         patch.dict("os.environ", {"UE_56_PATH": "C:/UE"}), \
         patch("os.path.isdir", return_value=True):
        result = await check_editor_status(str(tmp_path))

    assert result["running"] is True
    assert result["port"] == 9000
