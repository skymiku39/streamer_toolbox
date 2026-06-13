from __future__ import annotations

import asyncio

from identity_oauth.env_provider import EnvTokenProvider
from identity_oauth.protocol import OAuthCredentials


class SyncEnvTokenProvider:
    """Blocking facade for sync consumers（如 twitch-connector）。"""

    def __init__(self, provider: EnvTokenProvider | None = None) -> None:
        self._provider = provider or EnvTokenProvider()

    def client_id(self) -> str:
        return self._provider.client_id

    def access_token(self) -> str:
        return self._load_credentials().access_token

    def sender_id(self) -> str:
        return self._provider.bot_id

    def validate(self) -> None:
        missing: list[str] = []
        if not self._provider.client_id:
            missing.append("TWITCH_CLIENT_ID")
        if not self._provider.bot_id:
            missing.append("TWITCH_BOT_ID")
        if not self._provider.client_secret:
            missing.append("TWITCH_CLIENT_SECRET")
        if missing:
            raise ValueError(f"Missing Twitch OAuth env: {', '.join(missing)}")
        credentials = self._load_credentials()
        if not credentials.access_token:
            raise ValueError("Missing valid TWITCH_ACCESS_TOKEN (refresh failed or not set)")

    def _load_credentials(self) -> OAuthCredentials:
        return asyncio.run(self._provider.get_credentials())
