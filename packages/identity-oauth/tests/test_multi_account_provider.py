from __future__ import annotations

import asyncio

import pytest

from identity_oauth.multi_account_provider import MultiAccountTokenProvider
from identity_oauth.single_account import read_single_account_mode, resolve_refresh_token


def _env(**overrides: str) -> dict[str, str]:
    base = {
        "TWITCH_CLIENT_ID": "client-id",
        "TWITCH_CLIENT_SECRET": "client-secret",
        "TWITCH_BOT_ID": "bot-1",
        "TWITCH_BROADCASTER_ID": "broadcaster-1",
        "TWITCH_CHANNEL_REFRESH_TOKEN": "channel-refresh",
        "TWITCH_BOT_REFRESH_TOKEN": "bot-refresh",
        "TWITCH_CHANNEL_ACCESS_TOKEN": "channel-access",
        "TWITCH_BOT_ACCESS_TOKEN": "bot-access",
        "TWITCH_BROADCASTER_TYPE": "affiliate",
    }
    base.update(overrides)
    return base


def test_resolve_refresh_token_dual_account() -> None:
    env = _env()
    assert resolve_refresh_token(env, "channel") == "channel-refresh"
    assert resolve_refresh_token(env, "bot") == "bot-refresh"


def test_resolve_refresh_token_legacy_fallback() -> None:
    env = _env(
        TWITCH_CHANNEL_REFRESH_TOKEN="",
        TWITCH_BOT_REFRESH_TOKEN="",
        TWITCH_REFRESH_TOKEN="legacy-refresh",
    )
    assert resolve_refresh_token(env, "channel") == "legacy-refresh"
    assert resolve_refresh_token(env, "bot") == "legacy-refresh"


def test_single_account_mirrors_channel_refresh() -> None:
    env = _env(TWITCH_SINGLE_ACCOUNT="true")
    assert read_single_account_mode(env) is True
    assert resolve_refresh_token(env, "bot") == "channel-refresh"


def test_get_credentials_returns_role_specific_access_token() -> None:
    provider = MultiAccountTokenProvider(environ=_env())
    channel = asyncio.run(provider.get_credentials("channel"))
    bot = asyncio.run(provider.get_credentials("bot"))
    assert channel.access_token == "channel-access"
    assert bot.access_token == "bot-access"
    assert channel.refresh_token == "channel-refresh"
    assert bot.refresh_token == "bot-refresh"


def test_refresh_requires_role_refresh_token() -> None:
    provider = MultiAccountTokenProvider(
        environ=_env(
            TWITCH_CHANNEL_ACCESS_TOKEN="",
            TWITCH_BOT_ACCESS_TOKEN="",
            TWITCH_CHANNEL_REFRESH_TOKEN="",
            TWITCH_BOT_REFRESH_TOKEN="",
            TWITCH_REFRESH_TOKEN="",
        ),
    )
    with pytest.raises(RuntimeError, match="TWITCH_BOT"):
        asyncio.run(provider.get_credentials("bot"))
