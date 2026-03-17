import pytest
from unittest.mock import patch, AsyncMock
from cortexbot.health.preflight import check_editor_alive, PreflightResult


@pytest.mark.asyncio
async def test_editor_alive_success():
    with patch("cortexbot.services.unreal.check_ue_health", new_callable=AsyncMock) as mock:
        mock.return_value = {"connected": True, "status": {}}
        result = await check_editor_alive("/project")
    assert result.passed is True


@pytest.mark.asyncio
async def test_editor_alive_failure():
    with patch("cortexbot.services.unreal.check_ue_health", new_callable=AsyncMock) as mock:
        mock.return_value = {"connected": False, "error": "Connection refused"}
        result = await check_editor_alive("/project")
    assert result.passed is False
    assert "refused" in result.reason
