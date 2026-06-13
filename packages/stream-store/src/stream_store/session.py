from __future__ import annotations

from datetime import UTC, datetime

from stream_store.store import StreamTextStore

# 舊版全域 checkpoint（僅讀取相容；新寫入改為 per-channel）
ACTIVE_SESSION_KEY = "active_session_id"
ACTIVE_SESSION_KEY_PREFIX = "active_session_id"


def normalize_channel(channel: str) -> str:
    return channel.lstrip("#").lower() or "unknown"


def checkpoint_key_for_channel(channel: str) -> str:
    return f"{ACTIVE_SESSION_KEY_PREFIX}:{normalize_channel(channel)}"


def resolve_session_id(
    *,
    channel: str,
    explicit_session_id: str | None = None,
    day: str | None = None,
) -> str:
    normalized = normalize_channel(channel)
    session_day = day or datetime.now(UTC).strftime("%Y%m%d")
    channel_based = f"{normalized}_{session_day}"
    if explicit_session_id:
        explicit = explicit_session_id.strip()
        if explicit.startswith(f"{normalized}_"):
            return explicit
        # 忽略與 channel 不符的 STREAM_SESSION_ID，避免多直播間混寫同一 session
        return channel_based
    return channel_based


def resolve_session_for_channel(
    store: StreamTextStore,
    channel: str,
    *,
    explicit_session_id: str | None = None,
) -> str | None:
    """依直播間 channel 解析 session_id，避免跨房間誤用 checkpoint。"""
    if explicit_session_id:
        normalized = normalize_channel(channel)
        explicit = explicit_session_id.strip()
        if normalized and explicit.startswith(f"{normalized}_"):
            return explicit

    normalized = normalize_channel(channel)
    if not normalized or normalized == "unknown":
        return _resolve_without_channel(store)

    per_channel = store.get_checkpoint(checkpoint_key_for_channel(channel))
    if per_channel:
        return per_channel

    legacy = store.get_checkpoint(ACTIVE_SESSION_KEY)
    if legacy and legacy.startswith(f"{normalized}_"):
        return legacy

    latest = store.latest_session_id_for_channel(channel)
    if latest:
        return latest

    return resolve_session_id(channel=channel)


def _resolve_without_channel(store: StreamTextStore) -> str | None:
    legacy = store.get_checkpoint(ACTIVE_SESSION_KEY)
    if legacy:
        return legacy
    return store.latest_session_id()


def set_active_session_for_channel(
    store: StreamTextStore,
    *,
    channel: str,
    session_id: str,
) -> None:
    store.set_checkpoint(checkpoint_key_for_channel(channel), session_id)
