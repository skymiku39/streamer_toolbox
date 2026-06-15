from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from emotes import EmoteRegistry, twitch_emote_cdn_url
from events import ChatMessageEvent, EventSubEvent, TOPIC_CHAT_MESSAGE, eventsub_topic

SCHEMA_VERSION = 1


def _iso(value: Any) -> str:
    if value is None:
        return datetime.now(UTC).isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    text = str(value).strip()
    return text or datetime.now(UTC).isoformat()


def _user_id(user: Any) -> str:
    if user is None:
        return ""
    return str(getattr(user, "id", "") or "").strip()


def _login_name(user: Any) -> str:
    if user is None:
        return ""
    return (
        str(getattr(user, "name", "") or getattr(user, "login", "") or getattr(user, "id", "")).strip()
    )


def _display_name(user: Any) -> str:
    if user is None:
        return ""
    return str(
        getattr(user, "display_name", None)
        or getattr(user, "name", None)
        or getattr(user, "login", None)
        or getattr(user, "id", "")
    ).strip()


def _build_emote_url_map(message: Any) -> dict[str, str]:
    emote_map: dict[str, str] = {}
    for fragment in getattr(message, "fragments", []) or []:
        if getattr(fragment, "type", "") != "emote":
            continue
        emote = getattr(fragment, "emote", None)
        if emote is None:
            continue
        emote_id = str(getattr(emote, "id", "")).strip()
        frag_text = str(getattr(fragment, "text", "") or "").strip()
        if not emote_id or not frag_text:
            continue
        formats = getattr(emote, "format", []) or []
        fmt = "animated" if "animated" in formats else "static"
        emote_map[frag_text] = twitch_emote_cdn_url(emote_id, animated=fmt == "animated")
    return emote_map


def _badges_from_chatter(chatter: Any) -> list[dict[str, str]]:
    badges: list[dict[str, str]] = []
    for badge in getattr(chatter, "badges", []) or []:
        badges.append(
            {
                "set_id": str(getattr(badge, "set_id", "")),
                "id": str(getattr(badge, "id", "")),
            }
        )
    return badges


def chat_message_from_eventsub(
    message: Any,
    *,
    default_channel: str = "",
    emote_registry: EmoteRegistry | None = None,
) -> ChatMessageEvent:
    chatter = getattr(message, "chatter", None)
    broadcaster = getattr(message, "broadcaster", None)
    channel = _login_name(broadcaster) or default_channel.lstrip("#")

    reply = getattr(message, "reply", None)
    reply_payload = None
    if reply is not None:
        reply_payload = {
            "parent_user": _login_name(getattr(reply, "parent_user", None)),
            "parent_body": str(getattr(reply, "parent_message_body", "") or ""),
        }

    source_broadcaster = getattr(message, "source_broadcaster", None)
    raw: dict[str, Any] = {
        "source": "twitch_eventsub",
        "message_type": "chat_message",
    }
    if source_broadcaster is not None:
        raw["shared_chat"] = True
        raw["source_channel"] = _login_name(source_broadcaster)

    content = str(getattr(message, "text", "") or "")
    emote_url_map = _build_emote_url_map(message)
    if emote_registry is not None:
        emote_url_map = emote_registry.enrich(content, emote_url_map)

    return ChatMessageEvent(
        schema_version=SCHEMA_VERSION,
        topic=TOPIC_CHAT_MESSAGE,
        platform="twitch",
        message_id=str(getattr(message, "id", "") or "").strip(),
        author_name=_display_name(chatter),
        login=_login_name(chatter),
        author_id=_user_id(chatter),
        content=content,
        timestamp=_iso(getattr(message, "timestamp", None)),
        channel=channel,
        badges=_badges_from_chatter(chatter),
        emote_url_map=emote_url_map,
        reply=reply_payload,
        raw=raw,
    )


def build_eventsub_event(
    event_type: str,
    *,
    broadcaster_id: str,
    user_id: str = "",
    user_name: str = "",
    timestamp: str | None = None,
    payload: dict[str, Any] | None = None,
) -> EventSubEvent:
    return EventSubEvent(
        schema_version=SCHEMA_VERSION,
        topic=eventsub_topic(event_type),
        platform="twitch",
        event_type=event_type,
        broadcaster_id=broadcaster_id,
        user_id=user_id,
        user_name=user_name,
        timestamp=timestamp or datetime.now(UTC).isoformat(),
        payload=payload or {},
    )


def eventsub_from_follow(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "follow",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        user_id=_user_id(getattr(payload, "user", None)),
        user_name=_login_name(getattr(payload, "user", None)),
        timestamp=_iso(getattr(payload, "followed_at", None)),
        payload={"followed_at": _iso(getattr(payload, "followed_at", None))},
    )


def eventsub_from_raid(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "raid",
        broadcaster_id=_user_id(getattr(payload, "to_broadcaster", None)),
        user_id=_user_id(getattr(payload, "from_broadcaster", None)),
        user_name=_login_name(getattr(payload, "from_broadcaster", None)),
        timestamp=_iso(getattr(payload, "created_at", None)),
        payload={
            "viewer_count": int(getattr(payload, "viewer_count", 0) or 0),
            "from_broadcaster_id": _user_id(getattr(payload, "from_broadcaster", None)),
            "to_broadcaster_id": _user_id(getattr(payload, "to_broadcaster", None)),
        },
    )


def eventsub_from_subscribe(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "subscribe",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        user_id=_user_id(getattr(payload, "user", None)),
        user_name=_login_name(getattr(payload, "user", None)),
        timestamp=_iso(getattr(payload, "created_at", None)),
        payload={
            "tier": str(getattr(payload, "tier", "") or ""),
            "gift": bool(getattr(payload, "gift", False)),
        },
    )


def eventsub_from_subscription_gift(payload: Any) -> EventSubEvent:
    user = getattr(payload, "user", None)
    anonymous = bool(getattr(payload, "anonymous", False))
    return build_eventsub_event(
        "subscription_gift",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        user_id="" if anonymous else _user_id(user),
        user_name="" if anonymous else _login_name(user),
        timestamp=_iso(getattr(payload, "created_at", None)),
        payload={
            "tier": str(getattr(payload, "tier", "") or ""),
            "total": int(getattr(payload, "total", 0) or 0),
            "anonymous": anonymous,
        },
    )


def eventsub_from_subscription_message(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "subscription_message",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        user_id=_user_id(getattr(payload, "user", None)),
        user_name=_login_name(getattr(payload, "user", None)),
        timestamp=_iso(getattr(payload, "created_at", None)),
        payload={
            "tier": str(getattr(payload, "tier", "") or ""),
            "cumulative_months": int(getattr(payload, "cumulative_months", 0) or 0),
            "text": str(getattr(payload, "text", "") or ""),
        },
    )


def eventsub_from_redemption(payload: Any) -> EventSubEvent:
    reward = getattr(payload, "reward", None)
    return build_eventsub_event(
        "redemption",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        user_id=_user_id(getattr(payload, "user", None)),
        user_name=_login_name(getattr(payload, "user", None)),
        timestamp=_iso(getattr(payload, "redeemed_at", None)),
        payload={
            "redemption_id": str(getattr(payload, "id", "") or ""),
            "reward_title": str(getattr(reward, "title", "") or ""),
            "reward_cost": int(getattr(reward, "cost", 0) or 0),
            "user_input": str(getattr(payload, "user_input", "") or ""),
        },
    )


def eventsub_from_bits(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "bits",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        user_id=_user_id(getattr(payload, "user", None)),
        user_name=_login_name(getattr(payload, "user", None)),
        timestamp=_iso(getattr(payload, "created_at", None)),
        payload={
            "bits": int(getattr(payload, "bits", 0) or 0),
            "type": str(getattr(payload, "type", "") or ""),
            "text": str(getattr(payload, "text", "") or ""),
        },
    )


def eventsub_from_stream_online(payload: Any) -> EventSubEvent:
    broadcaster = getattr(payload, "broadcaster", None)
    return build_eventsub_event(
        "stream_online",
        broadcaster_id=_user_id(broadcaster),
        user_name=_login_name(broadcaster),
        timestamp=_iso(getattr(payload, "started_at", None)),
        payload={
            "stream_id": str(getattr(payload, "id", "") or ""),
            "stream_type": str(getattr(payload, "type", "") or ""),
            "started_at": _iso(getattr(payload, "started_at", None)),
        },
    )


def eventsub_from_stream_offline(payload: Any) -> EventSubEvent:
    broadcaster = getattr(payload, "broadcaster", None)
    return build_eventsub_event(
        "stream_offline",
        broadcaster_id=_user_id(broadcaster),
        user_name=_login_name(broadcaster),
        timestamp=datetime.now(UTC).isoformat(),
        payload={},
    )


def eventsub_from_message_delete(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "message_delete",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        user_id=_user_id(getattr(payload, "user", None)),
        user_name=_login_name(getattr(payload, "user", None)),
        timestamp=datetime.now(UTC).isoformat(),
        payload={"message_id": str(getattr(payload, "message_id", "") or "")},
    )


def eventsub_from_ban(payload: Any) -> EventSubEvent:
    ends_at = getattr(payload, "ends_at", None)
    return build_eventsub_event(
        "ban",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        user_id=_user_id(getattr(payload, "user", None)),
        user_name=_login_name(getattr(payload, "user", None)),
        timestamp=_iso(getattr(payload, "created_at", None)),
        payload={
            "moderator_id": _user_id(getattr(payload, "moderator", None)),
            "moderator_name": _login_name(getattr(payload, "moderator", None)),
            "reason": str(getattr(payload, "reason", "") or ""),
            "permanent": bool(getattr(payload, "permanent", True)),
            "ends_at": _iso(ends_at) if ends_at is not None else None,
        },
    )


def eventsub_from_unban(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "unban",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        user_id=_user_id(getattr(payload, "user", None)),
        user_name=_login_name(getattr(payload, "user", None)),
        timestamp=_iso(getattr(payload, "created_at", None)),
        payload={
            "moderator_id": _user_id(getattr(payload, "moderator", None)),
            "moderator_name": _login_name(getattr(payload, "moderator", None)),
        },
    )


def eventsub_from_automod_hold(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "automod_message_hold",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        user_id=_user_id(getattr(payload, "user", None)),
        user_name=_login_name(getattr(payload, "user", None)),
        timestamp=datetime.now(UTC).isoformat(),
        payload={
            "message_id": str(getattr(payload, "message_id", "") or ""),
            "text": str(getattr(payload, "text", "") or ""),
            "reason": str(getattr(payload, "reason", "") or ""),
            "category": str(getattr(payload, "category", "") or ""),
        },
    )


def eventsub_from_automod_update(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "automod_message_update",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        user_id=_user_id(getattr(payload, "moderator", None)),
        user_name=_login_name(getattr(payload, "moderator", None)),
        timestamp=datetime.now(UTC).isoformat(),
        payload={
            "message_id": str(getattr(payload, "message_id", "") or ""),
            "status": str(getattr(payload, "status", "") or ""),
        },
    )


def eventsub_from_poll_begin(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "poll_begin",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        timestamp=_iso(getattr(payload, "started_at", None)),
        payload={"poll_id": str(getattr(payload, "id", "") or "")},
    )


def eventsub_from_poll_progress(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "poll_progress",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        timestamp=datetime.now(UTC).isoformat(),
        payload={"poll_id": str(getattr(payload, "id", "") or "")},
    )


def eventsub_from_poll_end(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "poll_end",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        timestamp=_iso(getattr(payload, "ended_at", None)),
        payload={
            "poll_id": str(getattr(payload, "id", "") or ""),
            "status": str(getattr(payload, "status", "") or ""),
        },
    )


def eventsub_from_prediction_begin(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "prediction_begin",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        timestamp=_iso(getattr(payload, "started_at", None)),
        payload={"prediction_id": str(getattr(payload, "id", "") or "")},
    )


def eventsub_from_prediction_progress(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "prediction_progress",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        timestamp=datetime.now(UTC).isoformat(),
        payload={"prediction_id": str(getattr(payload, "id", "") or "")},
    )


def eventsub_from_prediction_lock(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "prediction_lock",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        timestamp=_iso(getattr(payload, "locked_at", None)),
        payload={"prediction_id": str(getattr(payload, "id", "") or "")},
    )


def eventsub_from_prediction_end(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "prediction_end",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        timestamp=_iso(getattr(payload, "ended_at", None)),
        payload={
            "prediction_id": str(getattr(payload, "id", "") or ""),
            "status": str(getattr(payload, "status", "") or ""),
            "winning_outcome_id": str(getattr(payload, "winning_outcome_id", "") or ""),
        },
    )


def eventsub_from_hype_train_begin(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "hype_train_begin",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        timestamp=_iso(getattr(payload, "started_at", None)),
        payload={
            "hype_train_id": str(getattr(payload, "id", "") or ""),
            "level": int(getattr(payload, "level", 0) or 0),
        },
    )


def eventsub_from_hype_train_progress(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "hype_train_progress",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        timestamp=datetime.now(UTC).isoformat(),
        payload={
            "hype_train_id": str(getattr(payload, "id", "") or ""),
            "level": int(getattr(payload, "level", 0) or 0),
            "total": int(getattr(payload, "total", 0) or 0),
        },
    )


def eventsub_from_hype_train_end(payload: Any) -> EventSubEvent:
    return build_eventsub_event(
        "hype_train_end",
        broadcaster_id=_user_id(getattr(payload, "broadcaster", None)),
        timestamp=_iso(getattr(payload, "ended_at", None)),
        payload={
            "hype_train_id": str(getattr(payload, "id", "") or ""),
            "level": int(getattr(payload, "level", 0) or 0),
            "total": int(getattr(payload, "total", 0) or 0),
        },
    )


def eventsub_from_first_chat(
    *,
    broadcaster_id: str,
    user_id: str,
    user_name: str,
    channel: str,
    stream_id: str = "",
) -> EventSubEvent:
    return build_eventsub_event(
        "first_chat",
        broadcaster_id=broadcaster_id,
        user_id=user_id,
        user_name=user_name,
        timestamp=datetime.now(UTC).isoformat(),
        payload={
            "channel": channel,
            "stream_id": stream_id,
        },
    )
