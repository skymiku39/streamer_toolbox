import json

import pytest
from events import TOPIC_CHAT_MESSAGE, ChatMessageEvent


def _sample_payload() -> dict:
    return {
        "schema_version": 1,
        "topic": TOPIC_CHAT_MESSAGE,
        "platform": "twitch",
        "message_id": "abc123",
        "author_id": "12345",
        "author_name": "觀眾暱稱",
        "login": "viewer_login",
        "content": "訊息正文",
        "timestamp": "2026-06-12T17:00:00+08:00",
        "channel": "channel_name",
        "badges": [],
        "emote_url_map": {},
        "reply": None,
        "raw": {},
    }


def test_round_trip_json() -> None:
    event = ChatMessageEvent.from_dict(_sample_payload())
    restored = ChatMessageEvent.from_json(event.to_json())
    assert restored == event


def test_to_dict_matches_events_contract() -> None:
    event = ChatMessageEvent.from_dict(_sample_payload())
    payload = event.to_dict()
    assert payload["schema_version"] == 1
    assert payload["topic"] == "chat.message"
    assert payload["platform"] == "twitch"
    assert payload["content"] == "訊息正文"


def test_from_json_bytes() -> None:
    raw = json.dumps(_sample_payload()).encode("utf-8")
    event = ChatMessageEvent.from_json(raw)
    assert event.message_id == "abc123"


@pytest.mark.parametrize(
    "field_name",
    ["message_id", "author_name", "content", "timestamp"],
)
def test_required_fields(field_name: str) -> None:
    payload = _sample_payload()
    payload[field_name] = ""
    with pytest.raises(ValueError):
        ChatMessageEvent.from_dict(payload)


def test_invalid_platform() -> None:
    payload = _sample_payload()
    payload["platform"] = "unknown"
    with pytest.raises(ValueError, match="platform"):
        ChatMessageEvent.from_dict(payload)


def test_invalid_topic() -> None:
    payload = _sample_payload()
    payload["topic"] = "chat.reply"
    with pytest.raises(ValueError, match="topic"):
        ChatMessageEvent.from_dict(payload)
