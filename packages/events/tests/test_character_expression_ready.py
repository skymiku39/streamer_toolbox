import json

import pytest
from events import TOPIC_CHARACTER_EXPRESSION_READY, CharacterExpressionReadyEvent


def _sample_payload() -> dict:
    return {
        "schema_version": 1,
        "topic": TOPIC_CHARACTER_EXPRESSION_READY,
        "turn_id": "turn-abc",
        "driver": "vts",
        "parameters": {"mouth_smile": 0.9},
    }


def test_round_trip_json() -> None:
    event = CharacterExpressionReadyEvent.from_dict(_sample_payload())
    restored = CharacterExpressionReadyEvent.from_json(event.to_json())
    assert restored == event


def test_from_json_bytes() -> None:
    raw = json.dumps(_sample_payload()).encode("utf-8")
    event = CharacterExpressionReadyEvent.from_json(raw)
    assert event.driver == "vts"


@pytest.mark.parametrize("field_name", ["turn_id"])
def test_required_fields(field_name: str) -> None:
    payload = _sample_payload()
    payload[field_name] = ""
    with pytest.raises(ValueError):
        CharacterExpressionReadyEvent.from_dict(payload)


def test_invalid_driver() -> None:
    payload = _sample_payload()
    payload["driver"] = "unknown"
    with pytest.raises(ValueError, match="driver"):
        CharacterExpressionReadyEvent.from_dict(payload)
