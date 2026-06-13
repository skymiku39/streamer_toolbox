import json

import pytest

from pkg_events import TOPIC_STT_SEGMENT, SttSegmentEvent


def _sample_payload() -> dict:
    return {
        "schema_version": 1,
        "topic": TOPIC_STT_SEGMENT,
        "platform": "twitch",
        "channel": "channel_name",
        "segment_id": "seg-abc123",
        "text": "辨識出的文字",
        "start_sec": 120.5,
        "end_sec": 125.0,
        "language": "zh",
        "confidence": 0.92,
        "highlight_score": 0.0,
        "timestamp": "2026-06-12T17:00:00+08:00",
    }


def test_round_trip_json() -> None:
    event = SttSegmentEvent.from_dict(_sample_payload())
    restored = SttSegmentEvent.from_json(event.to_json())
    assert restored == event


def test_to_dict_matches_events_contract() -> None:
    event = SttSegmentEvent.from_dict(_sample_payload())
    payload = event.to_dict()
    assert payload["schema_version"] == 1
    assert payload["topic"] == "stt.segment"
    assert payload["platform"] == "twitch"
    assert payload["text"] == "辨識出的文字"


def test_from_json_bytes() -> None:
    raw = json.dumps(_sample_payload()).encode("utf-8")
    event = SttSegmentEvent.from_json(raw)
    assert event.segment_id == "seg-abc123"


@pytest.mark.parametrize(
    "field_name",
    ["channel", "segment_id", "text", "timestamp"],
)
def test_required_fields(field_name: str) -> None:
    payload = _sample_payload()
    payload[field_name] = ""
    with pytest.raises(ValueError):
        SttSegmentEvent.from_dict(payload)


def test_invalid_platform() -> None:
    payload = _sample_payload()
    payload["platform"] = "unknown"
    with pytest.raises(ValueError, match="platform"):
        SttSegmentEvent.from_dict(payload)


def test_invalid_topic() -> None:
    payload = _sample_payload()
    payload["topic"] = "chat.message"
    with pytest.raises(ValueError, match="topic"):
        SttSegmentEvent.from_dict(payload)
