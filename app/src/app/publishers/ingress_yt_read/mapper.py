from __future__ import annotations

from tubechat_lens.reader import ChatMessage

from emotes.youtube import build_youtube_emote_url_map
from events import TOPIC_CHAT_MESSAGE, ChatMessageEvent

SCHEMA_VERSION = 1

_SUPER_CHAT_TYPES = frozenset({"superChat", "superSticker"})


def _build_badges(message: ChatMessage) -> list[dict[str, str]]:
    badges: list[dict[str, str]] = []
    if message.is_owner:
        badges.append({"type": "owner"})
    if message.is_moderator:
        badges.append({"type": "moderator"})
    if message.is_member:
        badges.append({"type": "member"})
    if message.is_verified:
        badges.append({"type": "verified"})
    return badges


def _resolve_content(message: ChatMessage) -> str:
    text = (message.message or "").strip()
    if text:
        return text
    if message.message_type in _SUPER_CHAT_TYPES and message.amount:
        label = "Super Chat" if message.message_type == "superChat" else "Super Sticker"
        return f"[{label} {message.amount}]"
    if message.message_type == "membershipItem":
        return "[membership]"
    return f"[{message.message_type}]"


def _build_raw(message: ChatMessage) -> dict[str, object]:
    raw: dict[str, object] = {
        "message_type": message.message_type,
        "source": "youtube_live_chat",
    }
    if message.amount:
        raw["amount"] = message.amount
    if isinstance(message.raw, dict) and message.raw:
        raw["pytchat"] = message.raw
    return raw


def map_chat_message(message: ChatMessage, channel: str) -> ChatMessageEvent:
    """將 tubechat_lens.ChatMessage 對齊 events.md chat.message 契約。"""

    pytchat_raw = message.raw if isinstance(message.raw, dict) else {}
    content = _resolve_content(message)
    emote_url_map = build_youtube_emote_url_map(pytchat_raw, content)

    return ChatMessageEvent(
        schema_version=SCHEMA_VERSION,
        topic=TOPIC_CHAT_MESSAGE,
        platform="youtube",
        message_id=message.message_id,
        author_name=message.author_name,
        author_id=message.author_id or None,
        content=content,
        timestamp=message.timestamp.isoformat(),
        channel=channel,
        badges=_build_badges(message),
        emote_url_map=emote_url_map,
        raw=_build_raw(message),
    )
