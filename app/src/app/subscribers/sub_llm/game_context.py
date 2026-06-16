from __future__ import annotations

import os

from game_info import GameInfoProvider, IgdbGameInfoProvider, format_game_info_for_prompt
from sub_llm.context_buffer import LiveContextBuffer

_NON_GAME_CATEGORIES = frozenset(
    {
        "just chatting",
        "music",
        "art",
        "special events",
        "sports",
        "travel & outdoors",
        "asmr",
        "talk shows",
        "food & drink",
        "makers & crafting",
    }
)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def create_game_info_provider() -> GameInfoProvider | None:
    """依環境變數建立 IGDB 查詢器；未啟用或缺憑證時回傳 None。"""
    if not _env_bool("LLM_GAME_INFO_ENABLED", True):
        return None
    client_id = (os.environ.get("TWITCH_CLIENT_ID") or "").strip()
    client_secret = (os.environ.get("TWITCH_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        return None
    cache_ttl = int(os.environ.get("LLM_GAME_INFO_CACHE_TTL_SECONDS", "3600"))
    return IgdbGameInfoProvider(
        client_id=client_id,
        client_secret=client_secret,
        cache_ttl_seconds=cache_ttl,
    )


def is_playable_game_category(game_name: str) -> bool:
    return game_name.strip().lower() not in _NON_GAME_CATEGORIES


def should_enrich_game_context(question: str, game_name: str) -> bool:
    """判斷是否應附加遊戲評分／簡介到 prompt。

    直播中且為可玩遊戲分類時一律附加，讓 LLM 回答任何問題時都能參考正在玩的遊戲背景。
    """
    del question
    normalized_game = game_name.strip()
    if not normalized_game or not is_playable_game_category(normalized_game):
        return False
    return True


def resolve_live_game_name(context_buffer: LiveContextBuffer, channel: str) -> str | None:
    return context_buffer.live_game_name(channel)


def build_game_reference(
    question: str,
    *,
    game_name: str | None,
    provider: GameInfoProvider | None,
) -> str:
    if provider is None or not game_name:
        return ""
    if not should_enrich_game_context(question, game_name):
        return ""
    info = provider.lookup(game_name)
    if info is None:
        return ""
    return format_game_info_for_prompt(info)
