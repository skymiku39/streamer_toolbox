"""IRC USERNOTICE（raw.message_type）→ 規則引擎事件鍵。"""

from __future__ import annotations

from typing import Any

from events import ChatMessageEvent

IRC_MESSAGE_TYPE_TO_EVENT: dict[str, str] = {
    "sub": "subscribe",
    "resub": "subscription_message",
    "subgift": "subscription_gift",
    "submysterygift": "subscription_gift",
    "raid": "raid",
    "bitsbadgetier": "bits",
}


def irc_event_key(message: ChatMessageEvent) -> str | None:
    message_type = str(message.raw.get("message_type", "textMessage")).strip()
    return IRC_MESSAGE_TYPE_TO_EVENT.get(message_type)


def irc_template_kwargs(message: ChatMessageEvent, event_key: str) -> dict[str, Any]:
    raw = message.raw
    author = message.author_name
    login = message.login or author
    channel = message.channel or ""

    if event_key == "subscribe":
        tier = str(raw.get("amount") or "Tier 1")
        return {
            "subscriber_name": author,
            "tier": tier,
            "gift_suffix": "",
        }
    if event_key == "subscription_message":
        months = str(raw.get("amount") or "1 個月")
        return {
            "subscriber_name": author,
            "months": months,
            "tier": str(raw.get("tier") or "Tier 1"),
        }
    if event_key == "subscription_gift":
        total = str(raw.get("total") or raw.get("amount") or "1")
        return {
            "gifter_name": author,
            "total": total,
            "tier": str(raw.get("tier") or "Tier 1"),
        }
    if event_key == "raid":
        viewers = raw.get("viewer_count") or raw.get("msg-param-viewerCount") or "?"
        return {
            "raider_name": author,
            "viewer_count": viewers,
        }
    if event_key == "bits":
        bits = raw.get("bits") or raw.get("amount") or "0"
        return {
            "user_name": author,
            "bits": bits,
            "type": "cheer",
            "text": message.content,
        }
    if event_key == "first_chat":
        return {"user": author, "login": login, "channel": channel}
    return {"user_name": author, "author": author, "channel": channel}
