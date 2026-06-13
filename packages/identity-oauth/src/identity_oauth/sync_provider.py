from __future__ import annotations

import asyncio

from identity_oauth.multi_account_provider import MultiAccountTokenProvider
from identity_oauth.protocol import AccountRole, OAuthCredentials


class SyncEnvTokenProvider:
    """Blocking facade for sync consumers（如 twitch-connector）。"""

    def __init__(
        self,
        provider: MultiAccountTokenProvider | None = None,
        *,
        role: AccountRole = "bot",
    ) -> None:
        self._provider = provider or MultiAccountTokenProvider()
        self._role = role

    @property
    def role(self) -> AccountRole:
        return self._role

    def client_id(self) -> str:
        return self._provider.client_id

    def access_token(self) -> str:
        return self._load_credentials().access_token

    def sender_id(self) -> str:
        return self._provider.bot_id

    def validate(self, *, role: AccountRole | None = None) -> None:
        resolved_role = role or self._role
        missing: list[str] = []
        if not self._provider.client_id:
            missing.append("TWITCH_CLIENT_ID")
        if resolved_role == "bot" and not self._provider.bot_id:
            missing.append("TWITCH_BOT_ID")
        if resolved_role == "channel" and not self._provider.broadcaster_id:
            missing.append("TWITCH_BROADCASTER_ID")
        if not self._provider.client_secret:
            missing.append("TWITCH_CLIENT_SECRET")
        if missing:
            raise ValueError(f"Missing Twitch OAuth env: {', '.join(missing)}")
        credentials = self._load_credentials(resolved_role)
        if not credentials.access_token:
            raise ValueError(
                f"Missing valid access token for role={resolved_role} "
                "(refresh failed or not set)",
            )

    def _load_credentials(self, role: AccountRole | None = None) -> OAuthCredentials:
        return asyncio.run(self._provider.get_credentials(role or self._role))
