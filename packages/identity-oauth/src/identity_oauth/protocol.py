from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

AccountRole = Literal["channel", "bot"]


@dataclass(frozen=True)
class OAuthCredentials:
    client_id: str
    client_secret: str
    bot_id: str
    broadcaster_id: str
    access_token: str
    refresh_token: str
    broadcaster_type: str = ""


class TokenProvider(Protocol):
    @property
    def client_id(self) -> str: ...

    @property
    def client_secret(self) -> str: ...

    @property
    def bot_id(self) -> str: ...

    @property
    def broadcaster_id(self) -> str: ...

    @property
    def broadcaster_type(self) -> str: ...

    async def get_credentials(self, role: AccountRole = "bot") -> OAuthCredentials: ...
