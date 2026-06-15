from __future__ import annotations

import logging

import httpx

from emotes.http import fetch_json
from emotes.providers.base import EmoteProvider, ThirdPartyEmote

_log = logging.getLogger(__name__)

_GLOBAL_URL = "https://api.frankerfacez.com/v1/set/global"
_CHANNEL_URL = "https://api.betterttv.net/3/cached/frankerfacez/users/twitch/{user_id}"
_NATIVE_CHANNEL_URL = "https://api.frankerfacez.com/v1/room/id/{user_id}"


class FFZProvider(EmoteProvider):
    @property
    def provider_name(self) -> str:
        return "ffz"

    async def fetch_global_emotes(self, *, client: httpx.AsyncClient) -> list[ThirdPartyEmote]:
        try:
            status, data = await fetch_json(_GLOBAL_URL, client=client)
            if status != 200:
                _log.warning("FFZ global emotes: HTTP %d", status)
                return []
        except Exception as exc:
            _log.warning("FFZ global emotes failed: %s", exc)
            return []
        return self._parse_native_response(data)

    async def fetch_channel_emotes(
        self,
        twitch_user_id: str,
        *,
        client: httpx.AsyncClient,
    ) -> list[ThirdPartyEmote]:
        result = await self._fetch_native(twitch_user_id, client=client)
        if result:
            return result
        return await self._fetch_via_bttv(twitch_user_id, client=client)

    async def _fetch_native(
        self,
        twitch_user_id: str,
        *,
        client: httpx.AsyncClient,
    ) -> list[ThirdPartyEmote]:
        url = _NATIVE_CHANNEL_URL.format(user_id=twitch_user_id)
        try:
            status, data = await fetch_json(url, client=client)
            if status == 404:
                return []
            if status != 200:
                _log.warning("FFZ channel emotes: HTTP %d (%s)", status, url)
                return []
        except Exception as exc:
            _log.warning("FFZ channel emotes failed (%s): %s", url, exc)
            return []
        return self._parse_native_response(data)

    async def _fetch_via_bttv(
        self,
        twitch_user_id: str,
        *,
        client: httpx.AsyncClient,
    ) -> list[ThirdPartyEmote]:
        url = _CHANNEL_URL.format(user_id=twitch_user_id)
        try:
            status, data = await fetch_json(url, client=client)
            if status != 200:
                return []
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        return self._parse_bttv_cached(data)

    def _parse_native_response(self, data: dict | object) -> list[ThirdPartyEmote]:
        if not isinstance(data, dict):
            return []
        sets = data.get("sets", {})
        if not isinstance(sets, dict):
            return []

        result: list[ThirdPartyEmote] = []
        for emote_set in sets.values():
            if not isinstance(emote_set, dict):
                continue
            emoticons = emote_set.get("emoticons", [])
            if not isinstance(emoticons, list):
                continue
            for emote in emoticons:
                parsed = self._parse_ffz_emote(emote)
                if parsed is not None:
                    result.append(parsed)
        return result

    @staticmethod
    def _parse_ffz_emote(raw: dict | object) -> ThirdPartyEmote | None:
        if not isinstance(raw, dict):
            return None
        emote_id = str(raw.get("id", "")).strip()
        name = str(raw.get("name", "")).strip()
        if not emote_id or not name:
            return None

        urls = raw.get("urls", {})
        if not isinstance(urls, dict):
            return None
        image_url = ""
        for key in ("2", "1", "4"):
            val = urls.get(key) or urls.get(int(key)) if key.isdigit() else None
            if isinstance(val, str) and val.strip():
                image_url = val.strip()
                if not image_url.startswith("http"):
                    image_url = "https:" + image_url
                break
        if not image_url:
            return None

        return ThirdPartyEmote(
            id=emote_id,
            name=name,
            image_url=image_url,
            source="ffz",
        )

    def _parse_bttv_cached(self, data: list) -> list[ThirdPartyEmote]:
        result: list[ThirdPartyEmote] = []
        for raw in data:
            if not isinstance(raw, dict):
                continue
            emote_id = str(raw.get("id", "")).strip()
            code = str(raw.get("code", "")).strip()
            if not emote_id or not code:
                continue
            images = raw.get("images", {})
            image_url = ""
            if isinstance(images, dict):
                for key in ("2x", "1x", "4x"):
                    val = images.get(key)
                    if isinstance(val, str) and val.strip():
                        image_url = val.strip()
                        break
            if not image_url:
                continue
            result.append(
                ThirdPartyEmote(
                    id=emote_id,
                    name=code,
                    image_url=image_url,
                    source="ffz",
                )
            )
        return result
