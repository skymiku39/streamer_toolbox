from __future__ import annotations

import asyncio
import logging
import os
import re

import httpx

from emotes.badges import parse_badge_response
from emotes.helix import fetch_app_access_token, helix_get, resolve_user_login_to_id
from emotes.providers import ALL_PROVIDERS
from emotes.providers.base import ThirdPartyEmote

_log = logging.getLogger(__name__)

_PROVIDER_PRIORITY = {"bttv": 10, "ffz": 20, "7tv": 30}
_DEFAULT_ENABLED = {"bttv": True, "ffz": True, "7tv": True}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _read_provider_toggles() -> dict[str, bool]:
    toggles = dict(_DEFAULT_ENABLED)
    if _env_bool("EMOTE_PROVIDER_BTTV", True) is False:
        toggles["bttv"] = False
    if _env_bool("EMOTE_PROVIDER_FFZ", True) is False:
        toggles["ffz"] = False
    if _env_bool("EMOTE_PROVIDER_7TV", True) is False:
        toggles["7tv"] = False
    return toggles


def _token_present(text: str, token: str) -> bool:
    if not token:
        return False
    if token.startswith(":"):
        return token in text
    pattern = rf"(?<!\S){re.escape(token)}(?!\S)"
    return re.search(pattern, text) is not None


def _merge_third_party_emotes(emotes: list[ThirdPartyEmote]) -> dict[str, str]:
    """Merge third-party emotes; earlier providers win on name conflict."""
    ordered = sorted(emotes, key=lambda item: _PROVIDER_PRIORITY.get(item.source, 100))
    merged: dict[str, str] = {}
    for emote in ordered:
        name = emote.name.strip()
        if not name or name in merged:
            continue
        merged[name] = emote.image_url
    return merged


class EmoteRegistry:
    """Cached third-party emote token -> image URL map for a Twitch channel."""

    def __init__(self, token_map: dict[str, str] | None = None) -> None:
        self._token_map = dict(token_map or {})

    @property
    def token_map(self) -> dict[str, str]:
        return dict(self._token_map)

    def enrich(self, content: str, native_map: dict[str, str] | None = None) -> dict[str, str]:
        merged = dict(native_map or {})
        for token, url in self._token_map.items():
            if token in merged:
                continue
            if _token_present(content, token):
                merged[token] = url
        return merged

    @classmethod
    async def load_for_user_id(
        cls,
        channel_user_id: str,
        *,
        enabled_providers: dict[str, bool] | None = None,
    ) -> EmoteRegistry:
        channel_user_id = str(channel_user_id).strip()
        if not channel_user_id:
            return cls()

        toggles = enabled_providers or _read_provider_toggles()
        providers = [
            provider_cls()
            for provider_cls in ALL_PROVIDERS
            if toggles.get(provider_cls().provider_name, True)
        ]
        if not providers:
            return cls()

        collected: list[ThirdPartyEmote] = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            global_lists = await asyncio.gather(
                *(provider.fetch_global_emotes(client=client) for provider in providers),
                return_exceptions=True,
            )
            channel_lists = await asyncio.gather(
                *(
                    provider.fetch_channel_emotes(channel_user_id, client=client)
                    for provider in providers
                ),
                return_exceptions=True,
            )

        for items in (*global_lists, *channel_lists):
            if isinstance(items, BaseException):
                _log.warning("third-party emote provider failed: %s", items)
                continue
            collected.extend(items)

        token_map = _merge_third_party_emotes(collected)
        _log.info(
            "loaded %d third-party emote tokens for channel user %s",
            len(token_map),
            channel_user_id,
        )
        return cls(token_map)

    @classmethod
    async def load_for_channel_login(
        cls,
        channel_login: str,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        enabled_providers: dict[str, bool] | None = None,
    ) -> EmoteRegistry:
        cid = (client_id or os.environ.get("TWITCH_CLIENT_ID") or "").strip()
        secret = (client_secret or os.environ.get("TWITCH_CLIENT_SECRET") or "").strip()
        broadcaster_id = (os.environ.get("TWITCH_BROADCASTER_ID") or "").strip()

        if broadcaster_id:
            return await cls.load_for_user_id(
                broadcaster_id,
                enabled_providers=enabled_providers,
            )

        if not cid or not secret:
            _log.info(
                "skip third-party emotes: missing TWITCH_CLIENT_ID/SECRET or TWITCH_BROADCASTER_ID"
            )
            return cls()

        async with httpx.AsyncClient(timeout=15.0) as client:
            token = await fetch_app_access_token(cid, secret, client=client)
            user_id = await resolve_user_login_to_id(
                channel_login,
                client_id=cid,
                access_token=token,
                client=client,
            )
        if not user_id:
            _log.warning(
                "skip third-party emotes: cannot resolve Twitch user id for %s", channel_login
            )
            return cls()
        return await cls.load_for_user_id(user_id, enabled_providers=enabled_providers)


class BadgeCatalog:
    """Helix global + channel badge image URLs."""

    def __init__(self, badge_urls: dict[str, str] | None = None) -> None:
        self._badge_urls = dict(badge_urls or {})

    @property
    def badge_urls(self) -> dict[str, str]:
        return dict(self._badge_urls)

    @classmethod
    async def load(
        cls,
        *,
        broadcaster_id: str,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> BadgeCatalog:
        cid = (client_id or os.environ.get("TWITCH_CLIENT_ID") or "").strip()
        secret = (client_secret or os.environ.get("TWITCH_CLIENT_SECRET") or "").strip()
        broadcaster_id = (broadcaster_id or os.environ.get("TWITCH_BROADCASTER_ID") or "").strip()
        if not cid or not secret or not broadcaster_id:
            _log.info("skip badge catalog: missing TWITCH credentials or TWITCH_BROADCASTER_ID")
            return cls()

        async with httpx.AsyncClient(timeout=15.0) as client:
            token = await fetch_app_access_token(cid, secret, client=client)
            global_resp, channel_resp = await asyncio.gather(
                helix_get(
                    "chat/badges/global",
                    client_id=cid,
                    access_token=token,
                    client=client,
                ),
                helix_get(
                    "chat/badges",
                    client_id=cid,
                    access_token=token,
                    client=client,
                    params={"broadcaster_id": broadcaster_id},
                ),
            )

        merged = {**parse_badge_response(global_resp), **parse_badge_response(channel_resp)}
        _log.info("loaded %d Twitch badge image URLs", len(merged))
        return cls(merged)

    @classmethod
    async def load_from_env(cls) -> BadgeCatalog:
        return await cls.load(broadcaster_id="")
