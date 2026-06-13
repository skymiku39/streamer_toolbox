from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TOKEN_MIN_TTL_SECONDS = 300


@dataclass
class RoleTokenState:
    refresh_token: str
    access_token: str = ""
    expires_at: float | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def is_access_token_fresh(self) -> bool:
        if not self.access_token or self.expires_at is None:
            return bool(self.access_token)
        return (self.expires_at - time.time()) > TOKEN_MIN_TTL_SECONDS


async def refresh_access_token(
    state: RoleTokenState,
    *,
    client_id: str,
    client_secret: str,
    role_label: str,
) -> None:
    async with state.lock:
        if state.is_access_token_fresh():
            return
        if not state.refresh_token:
            raise RuntimeError(
                f"{role_label} refresh token is required to refresh access token",
            )
        if not client_id or not client_secret:
            raise RuntimeError("TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET are required")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": state.refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()

        access_token = str(payload.get("access_token", "")).strip()
        if not access_token:
            raise RuntimeError(f"{role_label} token refresh response missing access_token")

        state.access_token = access_token
        refresh_token = str(payload.get("refresh_token", "")).strip()
        if refresh_token:
            state.refresh_token = refresh_token
        expires_in = payload.get("expires_in")
        if isinstance(expires_in, int | float) and expires_in > 0:
            state.expires_at = time.time() + float(expires_in)
        else:
            state.expires_at = None
