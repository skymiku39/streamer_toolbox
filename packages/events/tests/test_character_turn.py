import json

import pytest

from events import TOPIC_CHARACTER_TURN, CharacterTurnEvent


def _sample_payload() -> dict:
    return {
        "schema_version": 1,
        "topic": TOPIC_CHARACTER_TURN,
        "turn_id": "turn-abc",
        "correlation_id": "msg-xyz",
        "text": "角色要說的話",
        "emotion": "happy",
        "emotion_intensity": 0.8,
        "language": "zh-TW",
        "timestamp": "2026-06-12T17:00:00+08:00",
    }


def test_round_trip_json() -> None:
    event = CharacterTurnEvent.from_dict(_sample_payload())
    restored = CharacterTurnEvent.from_json(event.to_json())
    assert restored == event


def test_to_dict_matches_events_contract() -> None:
    event = CharacterTurnEvent.from_dict(_sample_payload())
    payload = event.to_dict()
    assert payload["schema_version"] == 1
    assert payload["topic"] == "character.turn"
    assert payload["turn_id"] == "turn-abc"
    assert payload["correlation_id"] == "msg-xyz"


def test_from_json_bytes() -> None:
    raw = json.dumps(_sample_payload()).encode("utf-8")
    event = CharacterTurnEvent.from_json(raw)
    assert event.text == "角色要說的話"


@pytest.mark.parametrize("field_name", ["turn_id", "correlation_id", "text", "timestamp"])
def test_required_fields(field_name: str) -> None:
    payload = _sample_payload()
    payload[field_name] = ""
    with pytest.raises(ValueError):
        CharacterTurnEvent.from_dict(payload)


def test_invalid_emotion() -> None:
    payload = _sample_payload()
    payload["emotion"] = "excited"
    with pytest.raises(ValueError, match="emotion"):
        CharacterTurnEvent.from_dict(payload)


def test_invalid_emotion_intensity() -> None:
    payload = _sample_payload()
    payload["emotion_intensity"] = 1.5
    with pytest.raises(ValueError, match="emotion_intensity"):
        CharacterTurnEvent.from_dict(payload)
