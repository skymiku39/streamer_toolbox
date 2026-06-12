from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from ingress_twitch_eventsub.bot import EventSubIngressBot
from ingress_twitch_eventsub.chat_status import CHAT_FALLBACK_EXIT_CODE, CHAT_INGRESS_IRC_FALLBACK


def _bot() -> EventSubIngressBot:
    return EventSubIngressBot(
        client_id="client",
        client_secret="secret",
        bot_id="bot-1",
        token="access",
        refresh_token="refresh",
        channels=["channel"],
        broadcaster_id="bc-1",
        broadcaster_type="affiliate",
        publisher=MagicMock(),
    )


def test_event_ready_exits_when_chat_read_unavailable(capsys: pytest.CaptureFixture[str]) -> None:
    bot = _bot()
    bot.chat_read_ok = False
    with pytest.raises(SystemExit) as exc_info:
        asyncio.run(bot.event_ready())
    assert exc_info.value.code == CHAT_FALLBACK_EXIT_CODE
    assert f"CHAT_INGRESS_STATUS={CHAT_INGRESS_IRC_FALLBACK}" in capsys.readouterr().out


def test_event_ready_reports_eventsub_when_chat_read_ok(capsys: pytest.CaptureFixture[str]) -> None:
    bot = _bot()
    bot.chat_read_ok = True
    asyncio.run(bot.event_ready())
    assert "CHAT_INGRESS_STATUS=eventsub" in capsys.readouterr().out
