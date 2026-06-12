from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx

from identity_oauth.protocol import OAuthCredentials

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TOKEN_MIN_TTL_SECONDS = 300


class EnvTokenProvider:
    """從環境變數載入 OAuth 憑證，並在需要時刷新 access token。"""

    def __init__(self, environ: dict[str, str] | None = None) -> None:
        self._environ = environ if environ is not None else os.environ
        self._access_token = (self._environ.get("TWITCH_ACCESS_TOKEN") or "").strip()
        self._refresh_token = (self._environ.get("TWITCH_REFRESH_TOKEN") or "").strip()
        self._expires_at: float | None = None
        self._refresh_lock = asyncio.Lock()

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

    def _is_access_token_fresh(self) -> bool:
        if not self._access_token or self._expires_at is None:
            return bool(self._access_token)
        return (self._expires_at - time.time()) > TOKEN_MIN_TTL_SECONDS

    async def get_credentials(self) -> OAuthCredentials:
        if not self._is_access_token_fresh():
            await self._refresh_access_token()
        return OAuthCredentials(
            client_id=self.client_id,
            client_secret=self.client_secret,
            bot_id=self.bot_id,
            broadcaster_id=self.broadcaster_id,
            access_token=self._access_token,
            refresh_token=self._refresh_token,
            broadcaster_type=self.broadcaster_type,
        )

    async def _refresh_access_token(self) -> None:
        async with self._refresh_lock:
            if self._is_access_token_fresh():
                return
            if not self._refresh_token:
                raise RuntimeError("TWITCH_REFRESH_TOKEN is required to refresh access token")
            if not self.client_id or not self.client_secret:
                raise RuntimeError("TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET are required")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    TOKEN_URL,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self._refresh_token,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                )
                response.raise_for_status()
                payload: dict[str, Any] = response.json()

            access_token = str(payload.get("access_token", "")).strip()
            if not access_token:
                raise RuntimeError("token refresh response missing access_token")

            self._access_token = access_token
            refresh_token = str(payload.get("refresh_token", "")).strip()
            if refresh_token:
                self._refresh_token = refresh_token
            expires_in = payload.get("expires_in")
            if isinstance(expires_in, int | float) and expires_in > 0:
                self._expires_at = time.time() + float(expires_in)
            else:
                self._expires_at = None
