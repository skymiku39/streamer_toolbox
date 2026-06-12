"""OAuth token 抽象；正式環境由 identity-oauth 注入。"""

from __future__ import annotations

import os
from typing import Protocol


class TokenProvider(Protocol):
    def client_id(self) -> str: ...

    def access_token(self) -> str: ...

    def sender_id(self) -> str: ...


class EnvTokenProvider:
    """從環境變數讀取 Twitch OAuth 憑證（過渡實作）。"""

    def __init__(
        self,
        *,
        client_id: str | None = None,
        access_token: str | None = None,
        sender_id: str | None = None,
    ) -> None:
        self._client_id = (client_id or os.environ.get("TWITCH_CLIENT_ID", "")).strip()
        self._access_token = (
            access_token
            or os.environ.get("TWITCH_ACCESS_TOKEN", "")
            or os.environ.get("TWITCH_BOT_ACCESS_TOKEN", "")
        ).strip()
        self._sender_id = (
            sender_id
            or os.environ.get("TWITCH_BOT_USER_ID", "")
            or os.environ.get("TWITCH_SENDER_ID", "")
        ).strip()

    def client_id(self) -> str:
        return self._client_id

    def access_token(self) -> str:
        return self._access_token

    def sender_id(self) -> str:
        return self._sender_id

    def validate(self) -> None:
        missing = []
        if not self._client_id:
            missing.append("TWITCH_CLIENT_ID")
        if not self._access_token:
            missing.append("TWITCH_ACCESS_TOKEN or TWITCH_BOT_ACCESS_TOKEN")
        if not self._sender_id:
            missing.append("TWITCH_BOT_USER_ID or TWITCH_SENDER_ID")
        if missing:
            raise ValueError(f"Missing Twitch OAuth env: {', '.join(missing)}")
