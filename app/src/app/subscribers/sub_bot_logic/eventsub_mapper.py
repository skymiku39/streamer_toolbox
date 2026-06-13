"""EventSub 正規化 payload → 模板變數。"""

from __future__ import annotations

from typing import Any

from pkg_events import EventSubEvent

EVENT_CATEGORY: dict[str, str] = {
    "follow": "event",
    "raid": "event",
    "subscribe": "event",
    "subscription_gift": "event",
    "subscription_message": "event",
    "bits": "event",
    "first_chat": "event",
    "redemption": "event",
    "message_delete": "moderation",
    "ban": "moderation",
    "unban": "moderation",
    "automod_message_hold": "moderation",
    "automod_message_update": "moderation",
    "poll_begin": "system",
    "poll_progress": "system",
    "poll_end": "system",
    "prediction_begin": "system",
    "prediction_progress": "system",
    "prediction_lock": "system",
    "prediction_end": "system",
    "hype_train_begin": "system",
    "hype_train_progress": "system",
    "hype_train_end": "system",
}

TEMPLATE_KEY_ALIASES: dict[str, str] = {
    "automod_message_hold": "automod_hold",
    "automod_message_update": "automod_update",
}


def template_category(event_type: str) -> str | None:
    return EVENT_CATEGORY.get(event_type)


def template_key(event_type: str) -> str:
    return TEMPLATE_KEY_ALIASES.get(event_type, event_type)


def _payload_get(event: EventSubEvent, *keys: str, default: Any = "") -> Any:
    data = event.payload
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return default


def template_kwargs(event: EventSubEvent) -> dict[str, Any]:
    event_type = event.event_type
    user = event.user_name or ""
    payload = event.payload

    if event_type == "follow":
        return {"follower_name": user or _payload_get(event, "follower_name")}
    if event_type == "raid":
        return {
            "raider_name": user or _payload_get(event, "raider_name"),
            "viewer_count": _payload_get(event, "viewer_count", "viewers", default="?"),
        }
    if event_type == "subscribe":
        return {
            "subscriber_name": user or _payload_get(event, "subscriber_name"),
            "tier": _payload_get(event, "tier", default="Tier 1"),
            "gift_suffix": _payload_get(event, "gift_suffix", default=""),
        }
    if event_type == "subscription_gift":
        return {
            "gifter_name": user or _payload_get(event, "gifter_name"),
            "total": _payload_get(event, "total", default="1"),
            "tier": _payload_get(event, "tier", default="Tier 1"),
        }
    if event_type == "subscription_message":
        return {
            "subscriber_name": user or _payload_get(event, "subscriber_name"),
            "months": _payload_get(event, "months", default="1 個月"),
            "tier": _payload_get(event, "tier", default="Tier 1"),
        }
    if event_type == "bits":
        text = str(_payload_get(event, "text", default=""))
        return {
            "user_name": user or _payload_get(event, "user_name"),
            "bits": _payload_get(event, "bits", default="0"),
            "type": _payload_get(event, "type", default="cheer"),
            "text": f"：{text}" if text else "",
        }
    if event_type == "first_chat":
        channel = event.channel or _payload_get(event, "channel")
        return {
            "user": user or _payload_get(event, "user"),
            "login": _payload_get(event, "login", default=user),
            "channel": channel,
        }
    if event_type == "redemption":
        return {
            "user": user or _payload_get(event, "user", "redeemer"),
            "title": _payload_get(event, "reward_title", "title"),
            "cost": _payload_get(event, "reward_cost", "cost", default=0),
            "user_input": _payload_get(event, "user_input", default=""),
        }
    if event_type == "message_delete":
        return {"target_user": _payload_get(event, "target_user", default=user)}
    if event_type == "ban":
        reason = str(_payload_get(event, "reason", default=""))
        return {
            "moderator": _payload_get(event, "moderator", default="管理員"),
            "banned_user": _payload_get(event, "banned_user", default=user),
            "action": _payload_get(event, "action", default="封鎖"),
            "reason_suffix": f"（{reason}）" if reason else "",
        }
    if event_type == "unban":
        return {
            "moderator": _payload_get(event, "moderator", default="管理員"),
            "unbanned_user": _payload_get(event, "unbanned_user", default=user),
        }
    if event_type in {"automod_message_hold", "automod_message_update"}:
        return {
            "user_name": user or _payload_get(event, "user_name"),
            "text": _payload_get(event, "text", default=""),
            "moderator": _payload_get(event, "moderator", default="管理員"),
            "status": _payload_get(event, "status", default="處理"),
        }
    if event_type.startswith("poll_"):
        return {
            "title": _payload_get(event, "title", default="投票"),
            "choices": _payload_get(event, "choices", default=""),
            "status": _payload_get(event, "status", default=""),
        }
    if event_type.startswith("prediction_"):
        return {
            "title": _payload_get(event, "title", default="預測"),
            "outcomes": _payload_get(event, "outcomes", default=""),
            "status": _payload_get(event, "status", default=""),
        }
    if event_type.startswith("hype_train_"):
        return {
            "level": _payload_get(event, "level", default="1"),
            "total": _payload_get(event, "total", default="0"),
        }
    return dict(payload)
