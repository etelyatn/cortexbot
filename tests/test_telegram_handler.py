import pytest
from unittest.mock import AsyncMock
from cortexbot.events.telegram_handler import TelegramEventHandler


@pytest.mark.asyncio
async def test_task_created_event():
    bot = AsyncMock()
    handler = TelegramEventHandler(bot)
    await handler.on_task_created({
        "task_id": "42",
        "description": "Add inventory",
        "chat_id": -100123,
        "thread_id": 42,
    })
    bot.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_session_completed_event():
    bot = AsyncMock()
    handler = TelegramEventHandler(bot)
    await handler.on_session_completed({
        "task_id": "42",
        "action": "plan",
        "exit_reason": "completed",
        "chat_id": -100123,
        "thread_id": 42,
    })
    bot.send_message.assert_called_once()
