import pytest

from events import TOPIC_CONFIG_CHANGED, ConfigChangedEvent


def _sample_payload() -> dict:
    return {
        "schema_version": 1,
        "topic": TOPIC_CONFIG_CHANGED,
        "module_id": "rule-bot",
        "profile_id": "default",
        "config_file": "bot_responses.json",
        "timestamp": "2026-06-15T10:00:00+08:00",
    }


def test_round_trip_json() -> None:
    event = ConfigChangedEvent.from_dict(_sample_payload())
    restored = ConfigChangedEvent.from_json(event.to_json())
    assert restored == event


def test_build_defaults() -> None:
    event = ConfigChangedEvent.build(
        module_id="llm-bot",
        config_file="llm_subscriber.json",
    )
    assert event.topic == TOPIC_CONFIG_CHANGED
    assert event.profile_id == "default"
    assert event.module_id == "llm-bot"


@pytest.mark.parametrize("field_name", ["module_id", "profile_id", "config_file", "timestamp"])
def test_required_fields(field_name: str) -> None:
    payload = _sample_payload()
    payload[field_name] = ""
    with pytest.raises(ValueError):
        ConfigChangedEvent.from_dict(payload)
