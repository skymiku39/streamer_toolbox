from __future__ import annotations

import asyncio

import pytest

from identity_oauth.env_provider import EnvTokenProvider


def _env(**overrides: str) -> dict[str, str]:
    base = {
        "TWITCH_CLIENT_ID": "client-id",
        "TWITCH_CLIENT_SECRET": "client-secret",
        "TWITCH_BOT_ID": "bot-1",
        "TWITCH_BROADCASTER_ID": "broadcaster-1",
        "TWITCH_ACCESS_TOKEN": "access-token",
        "TWITCH_REFRESH_TOKEN": "refresh-token",
        "TWITCH_BROADCASTER_TYPE": "affiliate",
    }
    base.update(overrides)
    return base


def test_get_credentials_uses_env_access_token() -> None:
    provider = EnvTokenProvider(environ=_env())
    creds = asyncio.run(provider.get_credentials())
    assert creds.access_token == "access-token"
    assert creds.bot_id == "bot-1"
    assert creds.broadcaster_type == "affiliate"


def test_refresh_requires_refresh_token() -> None:
    provider = EnvTokenProvider(environ=_env(TWITCH_ACCESS_TOKEN="", TWITCH_REFRESH_TOKEN=""))
    with pytest.raises(RuntimeError, match="TWITCH_REFRESH_TOKEN"):
        asyncio.run(provider.get_credentials())
