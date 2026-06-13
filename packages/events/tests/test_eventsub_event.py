import json

import pytest

from pkg_events import EVENTSUB_EVENT_TYPES, EventSubEvent, eventsub_topic


def _sample_payload() -> dict:
    return {
        "schema_version": 1,
        "topic": "eventsub.follow",
        "platform": "twitch",
        "event_type": "follow",
        "broadcaster_id": "12345",
        "user_id": "67890",
        "user_name": "viewer_login",
        "timestamp": "2026-06-12T17:00:00+08:00",
        "payload": {"followed_at": "2026-06-12T17:00:00+08:00"},
    }


def test_eventsub_topic_helper() -> None:
    assert eventsub_topic("follow") == "eventsub.follow"


def test_registered_event_types_include_first_chat() -> None:
    assert "first_chat" in EVENTSUB_EVENT_TYPES
    assert "redemption" in EVENTSUB_EVENT_TYPES


def test_round_trip_json() -> None:
    event = EventSubEvent.from_dict(_sample_payload())
    restored = EventSubEvent.from_json(event.to_json())
    assert restored == event


def test_to_dict_matches_events_contract() -> None:
    event = EventSubEvent.from_dict(_sample_payload())
    payload = event.to_dict()
    assert payload["schema_version"] == 1
    assert payload["topic"] == "eventsub.follow"
    assert payload["event_type"] == "follow"


def test_from_json_bytes() -> None:
    raw = json.dumps(_sample_payload()).encode("utf-8")
    event = EventSubEvent.from_json(raw)
    assert event.user_id == "67890"


@pytest.mark.parametrize("field_name", ["broadcaster_id", "timestamp"])
def test_required_fields(field_name: str) -> None:
    payload = _sample_payload()
    payload[field_name] = ""
    with pytest.raises(ValueError):
        EventSubEvent.from_dict(payload)


def test_invalid_event_type() -> None:
    payload = _sample_payload()
    payload["event_type"] = "unknown"
    payload["topic"] = "eventsub.unknown"
    with pytest.raises(ValueError, match="event_type"):
        EventSubEvent.from_dict(payload)


def test_topic_must_match_event_type() -> None:
    payload = _sample_payload()
    payload["topic"] = "eventsub.raid"
    with pytest.raises(ValueError, match="topic"):
        EventSubEvent.from_dict(payload)
