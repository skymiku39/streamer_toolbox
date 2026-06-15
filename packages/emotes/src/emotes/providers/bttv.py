from __future__ import annotations

import logging

import httpx

from emotes.http import fetch_json
from emotes.providers.base import EmoteProvider, ThirdPartyEmote

_log = logging.getLogger(__name__)

_GLOBAL_URL = "https://api.betterttv.net/3/cached/emotes/global"
_CHANNEL_URL = "https://api.betterttv.net/3/cached/users/twitch/{user_id}"
_CDN = "https://cdn.betterttv.net/emote/{id}/2x"


class BTTVProvider(EmoteProvider):
    @property
    def provider_name(self) -> str:
        return "bttv"

    async def fetch_global_emotes(self, *, client: httpx.AsyncClient) -> list[ThirdPartyEmote]:
        try:
            status, data = await fetch_json(_GLOBAL_URL, client=client)
            if status != 200:
                _log.warning("BTTV global emotes: HTTP %d", status)
                return []
        except Exception as exc:
            _log.warning("BTTV global emotes failed: %s", exc)
            return []
        return self._parse_emotes(data)

    async def fetch_channel_emotes(
        self,
        twitch_user_id: str,
        *,
        client: httpx.AsyncClient,
    ) -> list[ThirdPartyEmote]:
        url = _CHANNEL_URL.format(user_id=twitch_user_id)
        try:
            status, data = await fetch_json(url, client=client)
            if status == 404:
                return []
            if status != 200:
                _log.warning("BTTV channel emotes (%s): HTTP %d", twitch_user_id, status)
                return []
        except Exception as exc:
            _log.warning("BTTV channel emotes failed: %s", exc)
            return []

        if not isinstance(data, dict):
            return []
        channel_emotes = self._parse_emotes(data.get("channelEmotes", []))
        shared_emotes = self._parse_emotes(data.get("sharedEmotes", []))
        return channel_emotes + shared_emotes

    def _parse_emotes(self, emotes: list | object) -> list[ThirdPartyEmote]:
        result: list[ThirdPartyEmote] = []
        if not isinstance(emotes, list):
            return result
        for raw in emotes:
            if not isinstance(raw, dict):
                continue
            emote_id = str(raw.get("id", "")).strip()
            code = str(raw.get("code", "")).strip()
            if not emote_id or not code:
                continue
            image_type = str(raw.get("imageType", "png")).lower()
            result.append(
                ThirdPartyEmote(
                    id=emote_id,
                    name=code,
                    image_url=_CDN.format(id=emote_id),
                    source="bttv",
                    animated=image_type == "gif",
                )
            )
        return result
