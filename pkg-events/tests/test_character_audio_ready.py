import json

import pytest

from pkg_events import TOPIC_CHARACTER_AUDIO_READY, CharacterAudioReadyEvent


def _sample_payload() -> dict:
    return {
        "schema_version": 1,
        "topic": TOPIC_CHARACTER_AUDIO_READY,
        "turn_id": "turn-abc",
        "audio_path": "/tmp/voice.wav",
        "duration_ms": 3200,
        "visemes": [{"t_ms": 0, "v": "aa"}],
    }


def test_round_trip_json() -> None:
    event = CharacterAudioReadyEvent.from_dict(_sample_payload())
    restored = CharacterAudioReadyEvent.from_json(event.to_json())
    assert restored == event


def test_from_json_bytes() -> None:
    raw = json.dumps(_sample_payload()).encode("utf-8")
    event = CharacterAudioReadyEvent.from_json(raw)
    assert event.turn_id == "turn-abc"


@pytest.mark.parametrize("field_name", ["turn_id", "audio_path"])
def test_required_fields(field_name: str) -> None:
    payload = _sample_payload()
    payload[field_name] = ""
    with pytest.raises(ValueError):
        CharacterAudioReadyEvent.from_dict(payload)
