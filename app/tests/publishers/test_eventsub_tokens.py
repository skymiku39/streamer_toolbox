from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from ingress_twitch_eventsub.bot import EventSubIngressBot


def test_setup_hook_registers_channel_token_when_different() -> None:
    bot = EventSubIngressBot(
        client_id="client",
        client_secret="secret",
        bot_id="bot-1",
        token="bot-access",
        refresh_token="bot-refresh",
        channel_token="channel-access",
        channel_refresh_token="channel-refresh",
        channels=["channel"],
        broadcaster_id="bc-1",
        broadcaster_type="affiliate",
        publisher=MagicMock(),
    )
    bot.add_token = AsyncMock()
    bot._register_all_subscriptions = AsyncMock()

    asyncio.run(bot.setup_hook())

    assert bot.add_token.await_count == 2
    bot.add_token.assert_any_await("bot-access", "bot-refresh")
    bot.add_token.assert_any_await("channel-access", "channel-refresh")
