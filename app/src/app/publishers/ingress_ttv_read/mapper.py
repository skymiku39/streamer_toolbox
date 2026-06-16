from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from events import TOPIC_CHAT_MESSAGE, ChatMessageEvent

from emotes import EmoteRegistry, parse_irc_emotes_tag
from ttvchat_lens import ChatMessage

_SKIP_MESSAGE_TYPES = frozenset(
    {
        "joined",
        "disconnected",
        "error",
        "notice",
        "reconnect",
        "system",
    }
)


def _fallback_message_id(msg: ChatMessage, channel: str) -> str:
    """Stable fallback when IRC lacks ``id`` tag (must not include timestamp)."""
    base = f"{channel}:{msg.message_type}:{msg.author_id}:{msg.message}"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]
    return f"irc-{digest}"


def _parse_badges(tags: dict[str, Any]) -> list[dict[str, str]]:
    badges_raw = tags.get("badges", "") or ""
    if not badges_raw:
        return []
    badges: list[dict[str, str]] = []
    for entry in badges_raw.split(","):
        if not entry:
            continue
        if "/" in entry:
            name, version = entry.split("/", 1)
            badges.append({"name": name, "version": version})
        else:
            badges.append({"name": entry, "version": "1"})
    return badges


def _build_raw(msg: ChatMessage) -> dict[str, Any]:
    raw: dict[str, Any] = dict(msg.raw) if msg.raw else {}
    raw["message_type"] = msg.message_type
    if msg.amount is not None:
        raw["amount"] = msg.amount
    if msg.bits:
        raw["bits"] = msg.bits
    return raw


def should_publish(msg: ChatMessage) -> bool:
    if msg.message_type in _SKIP_MESSAGE_TYPES:
        return False
    if not msg.message.strip():
        return False
    return True


def map_chat_message(
    msg: ChatMessage,
    channel: str,
    *,
    emote_registry: EmoteRegistry | None = None,
) -> ChatMessageEvent | None:
    """將 ttvchat_lens.ChatMessage 轉成 pkg-events ChatMessageEvent。"""
    if not should_publish(msg):
        return None

    message_id = msg.message_id.strip() or _fallback_message_id(msg, channel)
    tags = msg.raw if isinstance(msg.raw, dict) else {}
    emote_url_map = parse_irc_emotes_tag(str(tags.get("emotes", "") or ""), msg.message)
    if emote_registry is not None:
        emote_url_map = emote_registry.enrich(msg.message, emote_url_map)

    return ChatMessageEvent(
        schema_version=1,
        topic=TOPIC_CHAT_MESSAGE,
        platform="twitch",
        message_id=message_id,
        author_name=msg.author_name or "anonymous",
        author_id=msg.author_id or None,
        content=msg.message,
        timestamp=msg.timestamp.isoformat()
        if isinstance(msg.timestamp, datetime)
        else str(msg.timestamp),
        channel=channel,
        badges=_parse_badges(tags),
        emote_url_map=emote_url_map,
        raw=_build_raw(msg),
    )
