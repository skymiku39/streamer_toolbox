from __future__ import annotations

import logging

import httpx

from emotes.http import fetch_json
from emotes.providers.base import EmoteProvider, ThirdPartyEmote

_log = logging.getLogger(__name__)

_GLOBAL_URL = "https://7tv.io/v3/emote-sets/global"
_USER_URL = "https://7tv.io/v3/users/twitch/{user_id}"
_CDN = "https://cdn.7tv.app/emote/{id}/2x.webp"


class SevenTVProvider(EmoteProvider):
    @property
    def provider_name(self) -> str:
        return "7tv"

    async def fetch_global_emotes(self, *, client: httpx.AsyncClient) -> list[ThirdPartyEmote]:
        try:
            status, data = await fetch_json(_GLOBAL_URL, client=client)
            if status != 200:
                _log.warning("7TV global emotes: HTTP %d", status)
                return []
        except Exception as exc:
            _log.warning("7TV global emotes failed: %s", exc)
            return []

        emotes_raw = data.get("emotes", []) if isinstance(data, dict) else []
        return self._parse_emotes(emotes_raw)

    async def fetch_channel_emotes(
        self,
        twitch_user_id: str,
        *,
        client: httpx.AsyncClient,
    ) -> list[ThirdPartyEmote]:
        url = _USER_URL.format(user_id=twitch_user_id)
        try:
            status, data = await fetch_json(url, client=client)
            if status == 404:
                return []
            if status != 200:
                _log.warning("7TV channel emotes (%s): HTTP %d", twitch_user_id, status)
                return []
        except Exception as exc:
            _log.warning("7TV channel emotes failed: %s", exc)
            return []

        if not isinstance(data, dict):
            return []
        emote_set = data.get("emote_set", {})
        if not isinstance(emote_set, dict):
            return []
        emotes_raw = emote_set.get("emotes", [])
        return self._parse_emotes(emotes_raw)

    def _parse_emotes(self, emotes: list | object) -> list[ThirdPartyEmote]:
        result: list[ThirdPartyEmote] = []
        if not isinstance(emotes, list):
            return result
        for raw in emotes:
            if not isinstance(raw, dict):
                continue
            emote_id = str(raw.get("id", "")).strip()
            name = str(raw.get("name", "")).strip()
            if not emote_id or not name:
                continue

            image_url = _CDN.format(id=emote_id)
            animated = False
            emote_data = raw.get("data", {})
            if isinstance(emote_data, dict):
                animated = bool(emote_data.get("animated", False))
                host = emote_data.get("host", {})
                if isinstance(host, dict):
                    url_base = str(host.get("url", "")).strip()
                    files = host.get("files", [])
                    if isinstance(files, list) and url_base:
                        preferred = self._pick_file(files, animated=animated)
                        if preferred:
                            image_url = f"https:{url_base}/{preferred}"

            result.append(
                ThirdPartyEmote(
                    id=emote_id,
                    name=name,
                    image_url=image_url,
                    source="7tv",
                    animated=animated,
                )
            )
        return result

    @staticmethod
    def _pick_file(files: list, *, animated: bool = False) -> str:
        static_2x = ""
        gif_2x = ""
        avif_2x = ""
        any_2x = ""
        fallback = ""
        for item in files:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            fmt = str(item.get("format", "")).upper()
            if not name:
                continue
            if "2x" in name:
                if fmt == "WEBP":
                    static_2x = name
                if fmt == "GIF":
                    gif_2x = name
                if fmt == "AVIF":
                    avif_2x = name
                if not any_2x:
                    any_2x = name
            if not fallback:
                fallback = name
        if animated:
            return gif_2x or avif_2x or any_2x or fallback
        return static_2x or any_2x or fallback
