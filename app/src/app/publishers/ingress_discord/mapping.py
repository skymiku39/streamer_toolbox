from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from events import TOPIC_CHAT_MESSAGE, ChatMessageEvent

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DiscordChatMessage:
    message_id: str
    author_id: str
    author_name: str
    login: str
    content: str
    timestamp: str
    channel: str
    channel_id: str
    guild_id: str | None
    reply: dict[str, Any] | None
    raw: dict[str, Any]


def build_chat_event(discord_msg: DiscordChatMessage) -> ChatMessageEvent:
    return ChatMessageEvent(
        schema_version=SCHEMA_VERSION,
        topic=TOPIC_CHAT_MESSAGE,
        platform="discord",
        message_id=discord_msg.message_id,
        author_name=discord_msg.author_name,
        login=discord_msg.login,
        author_id=discord_msg.author_id,
        content=discord_msg.content,
        timestamp=discord_msg.timestamp,
        channel=discord_msg.channel,
        reply=discord_msg.reply,
        raw=discord_msg.raw,
    )


def parse_reply(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if not raw:
        return None
    message_id = raw.get("message_id")
    author_name = raw.get("author_name")
    if not message_id or not author_name:
        return None
    content = raw.get("content", "")
    return {
        "message_id": str(message_id),
        "author_name": str(author_name),
        "content": str(content),
    }
