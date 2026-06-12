"""OAuth token 抽象；正式環境由 identity-oauth 注入。"""

from __future__ import annotations

from typing import Protocol

from identity_oauth import SyncEnvTokenProvider

# 向後相容別名
EnvTokenProvider = SyncEnvTokenProvider


class TokenProvider(Protocol):
    def client_id(self) -> str: ...

    def access_token(self) -> str: ...

    def sender_id(self) -> str: ...

    def validate(self) -> None: ...
