from __future__ import annotations

import pytest

from identity_oauth.sync_provider import SyncEnvTokenProvider


def _env(**overrides: str) -> dict[str, str]:
    base = {
        "TWITCH_CLIENT_ID": "client-id",
        "TWITCH_CLIENT_SECRET": "client-secret",
        "TWITCH_BOT_ID": "bot-123",
        "TWITCH_ACCESS_TOKEN": "access-token",
        "TWITCH_REFRESH_TOKEN": "refresh-token",
    }
    base.update(overrides)
    return base


def test_sync_provider_exposes_connector_fields() -> None:
    from identity_oauth.multi_account_provider import MultiAccountTokenProvider

    provider = SyncEnvTokenProvider(
        MultiAccountTokenProvider(
            environ=_env(TWITCH_BOT_ACCESS_TOKEN="access-token", TWITCH_ACCESS_TOKEN=""),
        ),
        role="bot",
    )
    provider.validate()
    assert provider.client_id() == "client-id"
    assert provider.access_token() == "access-token"
    assert provider.sender_id() == "bot-123"


def test_validate_requires_bot_id() -> None:
    from identity_oauth.multi_account_provider import MultiAccountTokenProvider

    provider = SyncEnvTokenProvider(
        MultiAccountTokenProvider(environ=_env(TWITCH_BOT_ID="")),
        role="bot",
    )
    with pytest.raises(ValueError, match="TWITCH_BOT_ID"):
        provider.validate()
