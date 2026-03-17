import asyncio
import pytest
from unittest.mock import patch, MagicMock
from cortexbot.services.unreal import check_ue_health, run_ue_command


@pytest.mark.asyncio
async def test_check_ue_health_success():
    """Health check returns connected=True when UEConnection succeeds."""
    mock_conn = MagicMock()
    mock_conn.send_command.return_value = {"editor": "running"}

    with patch("cortexbot.services.unreal._make_connection", return_value=mock_conn):
        result = await check_ue_health("/some/project")

    assert result["connected"] is True
    assert result["status"] == {"editor": "running"}
    mock_conn.connect.assert_called_once()
    mock_conn.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_check_ue_health_failure():
    """Health check returns connected=False when connection fails."""
    mock_conn = MagicMock()
    mock_conn.connect.side_effect = ConnectionRefusedError("No editor")

    with patch("cortexbot.services.unreal._make_connection", return_value=mock_conn):
        result = await check_ue_health("/some/project")

    assert result["connected"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_run_ue_command_success():
    """run_ue_command sends domain.command and returns result."""
    mock_conn = MagicMock()
    mock_conn.send_command.return_value = {"tables": ["DT_Items"]}

    with patch("cortexbot.services.unreal._make_connection", return_value=mock_conn):
        result = await run_ue_command("/project", "data", "list_datatables", {})

    assert result == {"tables": ["DT_Items"]}
    mock_conn.send_command.assert_called_once_with("data.list_datatables", {})


@pytest.mark.asyncio
async def test_env_var_restored_after_call():
    """Environment variable is restored after UEConnection construction."""
    import os

    mock_conn = MagicMock()
    mock_conn.send_command.return_value = {}

    os.environ["CORTEX_PROJECT_DIR"] = "original"
    with patch("cortexbot.services.unreal.UEConnection", return_value=mock_conn):
        await check_ue_health("/some/project")

    assert os.environ.get("CORTEX_PROJECT_DIR") == "original"
    os.environ.pop("CORTEX_PROJECT_DIR", None)
