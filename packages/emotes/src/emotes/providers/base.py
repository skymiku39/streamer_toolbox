from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class ThirdPartyEmote:
    id: str
    name: str
    image_url: str
    source: str
    animated: bool = False


class EmoteProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    async def fetch_global_emotes(self, *, client: httpx.AsyncClient) -> list[ThirdPartyEmote]: ...

    @abstractmethod
    async def fetch_channel_emotes(
        self,
        twitch_user_id: str,
        *,
        client: httpx.AsyncClient,
    ) -> list[ThirdPartyEmote]: ...
