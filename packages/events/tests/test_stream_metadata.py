import json

import pytest

from events import TOPIC_STREAM_METADATA, StreamMetadataEvent


def _sample_payload() -> dict:
    return {
        "schema_version": 1,
        "topic": TOPIC_STREAM_METADATA,
        "platform": "twitch",
        "channel": "skymiku39",
        "timestamp": "2026-06-13T10:00:00+00:00",
        "snapshot_id": "abc123snapshot01",
        "is_live": True,
        "title": "測試直播標題",
        "game_name": "Just Chatting",
        "display_name": "Skymiku39",
        "started_at": "2026-06-13T08:00:00+00:00",
        "duration_seconds": 7200,
        "viewer_count": 128,
        "stream_url": "https://www.twitch.tv/skymiku39",
    }


def test_round_trip_json() -> None:
    event = StreamMetadataEvent.from_dict(_sample_payload())
    restored = StreamMetadataEvent.from_json(event.to_json())
    assert restored == event


def test_required_fields() -> None:
    payload = _sample_payload()
    payload.pop("snapshot_id")
    with pytest.raises(KeyError):
        StreamMetadataEvent.from_dict(payload)


def test_from_json_bytes() -> None:
    raw = json.dumps(_sample_payload()).encode("utf-8")
    event = StreamMetadataEvent.from_json(raw)
    assert event.game_name == "Just Chatting"
