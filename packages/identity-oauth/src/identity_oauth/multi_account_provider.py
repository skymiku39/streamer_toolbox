from __future__ import annotations

import os

from identity_oauth.protocol import AccountRole, OAuthCredentials
from identity_oauth.single_account import (
    read_single_account_mode,
    resolve_refresh_token,
    resolve_static_access_token,
)
from identity_oauth.token_refresh import RoleTokenState, refresh_access_token


class MultiAccountTokenProvider:
    """依 channel / bot 角色提供 Helix OAuth 憑證，對齊 twitch_api 雙帳號 env。"""

    def __init__(self, environ: dict[str, str] | None = None) -> None:
        self._environ = environ if environ is not None else os.environ
        self._states: dict[AccountRole, RoleTokenState] = {
            role: RoleTokenState(
                refresh_token=resolve_refresh_token(self._environ, role),
                access_token=resolve_static_access_token(self._environ, role),
            )
            for role in ("channel", "bot")
        }

    @property
    def client_id(self) -> str:
        return (self._environ.get("TWITCH_CLIENT_ID") or "").strip()

    @property
    def client_secret(self) -> str:
        return (self._environ.get("TWITCH_CLIENT_SECRET") or "").strip()

    @property
    def bot_id(self) -> str:
        return (self._environ.get("TWITCH_BOT_ID") or "").strip()

    @property
    def broadcaster_id(self) -> str:
        return (self._environ.get("TWITCH_BROADCASTER_ID") or "").strip()

    @property
    def broadcaster_type(self) -> str:
        return (self._environ.get("TWITCH_BROADCASTER_TYPE") or "").strip().lower()

    @property
    def single_account(self) -> bool:
        return read_single_account_mode(self._environ)

    async def get_credentials(self, role: AccountRole = "bot") -> OAuthCredentials:
        state = self._states[role]
        if not state.is_access_token_fresh():
            await refresh_access_token(
                state,
                client_id=self.client_id,
                client_secret=self.client_secret,
                role_label=f"TWITCH_{role.upper()}",
            )
        return OAuthCredentials(
            client_id=self.client_id,
            client_secret=self.client_secret,
            bot_id=self.bot_id,
            broadcaster_id=self.broadcaster_id,
            access_token=state.access_token,
            refresh_token=state.refresh_token,
            broadcaster_type=self.broadcaster_type,
        )
