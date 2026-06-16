import json

import pytest
from events import TOPIC_SYSTEM_ERROR, SystemErrorEvent


def _sample_payload() -> dict:
    return {
        "schema_version": 1,
        "topic": TOPIC_SYSTEM_ERROR,
        "component": "twitch-connector",
        "message": "send failed",
        "timestamp": "2026-06-12T17:00:00+08:00",
        "detail": {"channel": "test_channel"},
    }


def test_round_trip_json() -> None:
    event = SystemErrorEvent.from_dict(_sample_payload())
    restored = SystemErrorEvent.from_json(event.to_json())
    assert restored == event


def test_from_json_bytes() -> None:
    raw = json.dumps(_sample_payload()).encode("utf-8")
    event = SystemErrorEvent.from_json(raw)
    assert event.component == "twitch-connector"


@pytest.mark.parametrize("field_name", ["component", "message", "timestamp"])
def test_required_fields(field_name: str) -> None:
    payload = _sample_payload()
    payload[field_name] = ""
    with pytest.raises(ValueError):
        SystemErrorEvent.from_dict(payload)
