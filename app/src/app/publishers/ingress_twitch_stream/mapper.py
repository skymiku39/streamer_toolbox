from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from events import TOPIC_STREAM_METADATA, StreamMetadataEvent

from ingress_twitch_stream.fetcher import TwitchStreamSnapshot, elapsed_seconds


def build_stream_metadata_event(snapshot: TwitchStreamSnapshot) -> StreamMetadataEvent:
    fetched_at = snapshot.fetched_at
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)
    timestamp = fetched_at.isoformat()
    duration = (
        elapsed_seconds(snapshot.started_at, now=fetched_at)
        if snapshot.is_live
        else None
    )
    snapshot_id = _snapshot_id(snapshot, timestamp=timestamp, duration=duration)
    return StreamMetadataEvent(
        schema_version=1,
        topic=TOPIC_STREAM_METADATA,
        platform="twitch",
        channel=snapshot.channel,
        timestamp=timestamp,
        snapshot_id=snapshot_id,
        is_live=snapshot.is_live,
        title=snapshot.title,
        game_name=snapshot.game_name,
        display_name=snapshot.display_name,
        started_at=snapshot.started_at,
        duration_seconds=duration,
        viewer_count=snapshot.viewer_count,
        stream_url=snapshot.stream_url,
    )


def _snapshot_id(
    snapshot: TwitchStreamSnapshot,
    *,
    timestamp: str,
    duration: int | None,
) -> str:
    bucket_minute = timestamp[:16]
    duration_bucket = (duration // 60) if duration is not None else -1
    digest = hashlib.sha256(
        f"{snapshot.channel}|{snapshot.is_live}|{snapshot.title}|"
        f"{snapshot.game_name}|{duration_bucket}|{bucket_minute}".encode("utf-8")
    ).hexdigest()
    return digest[:16]
