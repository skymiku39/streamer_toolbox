import json

import pytest

from events import TOPIC_MEMORY_SUMMARIZE_REQUEST, MemorySummarizeRequestEvent


def _sample_payload() -> dict:
    return {
        "schema_version": 1,
        "topic": TOPIC_MEMORY_SUMMARIZE_REQUEST,
        "timestamp": "2026-06-12T17:00:00+08:00",
        "session_id": "demo_20260612",
        "reason": "manual",
        "source": "cli",
    }


def test_round_trip_json() -> None:
    event = MemorySummarizeRequestEvent.from_dict(_sample_payload())
    restored = MemorySummarizeRequestEvent.from_json(event.to_json())
    assert restored == event


def test_build_defaults() -> None:
    event = MemorySummarizeRequestEvent.build()
    assert event.topic == TOPIC_MEMORY_SUMMARIZE_REQUEST
    assert event.session_id is None
    assert event.reason == "manual"
    assert event.source == "cli"


@pytest.mark.parametrize("field_name", ["timestamp", "reason", "source"])
def test_required_fields(field_name: str) -> None:
    payload = _sample_payload()
    payload[field_name] = ""
    with pytest.raises(ValueError):
        MemorySummarizeRequestEvent.from_dict(payload)
