import json

import pytest

from events import TOPIC_CHAT_REPLY, ChatReplyEvent


def _sample_payload() -> dict:
    return {
        "schema_version": 1,
        "topic": TOPIC_CHAT_REPLY,
        "platform": "twitch",
        "channel": "channel_name",
        "content": "BOT 回覆文字",
        "reply_to_message_id": None,
        "sender": "bot",
        "source": "character-brain",
        "correlation_id": "msg-xyz",
    }


def test_round_trip_json() -> None:
    event = ChatReplyEvent.from_dict(_sample_payload())
    restored = ChatReplyEvent.from_json(event.to_json())
    assert restored == event


def test_to_dict_matches_events_contract() -> None:
    event = ChatReplyEvent.from_dict(_sample_payload())
    payload = event.to_dict()
    assert payload["source"] == "character-brain"
    assert payload["correlation_id"] == "msg-xyz"


def test_from_json_bytes() -> None:
    raw = json.dumps(_sample_payload()).encode("utf-8")
    event = ChatReplyEvent.from_json(raw)
    assert event.content == "BOT 回覆文字"


@pytest.mark.parametrize("field_name", ["channel", "content"])
def test_required_fields(field_name: str) -> None:
    payload = _sample_payload()
    payload[field_name] = ""
    with pytest.raises(ValueError):
        ChatReplyEvent.from_dict(payload)


def test_invalid_source() -> None:
    payload = _sample_payload()
    payload["source"] = "unknown"
    with pytest.raises(ValueError, match="source"):
        ChatReplyEvent.from_dict(payload)
