from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from events import TOPIC_CHAT_MESSAGE, ChatMessageEvent
from ttvchat_lens import ChatMessage

from ingress_ttv_read.mapper import map_chat_message, should_publish


def _text_message(**overrides) -> ChatMessage:
    defaults = {
        "message_id": "msg-001",
        "author_name": "Viewer",
        "author_id": "999",
        "message": "hello world",
        "timestamp": datetime(2026, 6, 12, 9, 0, 0, tzinfo=UTC),
        "message_type": "textMessage",
        "raw": {
            "id": "msg-001",
            "display-name": "Viewer",
            "user-id": "999",
            "badges": "subscriber/12,moderator/1",
        },
    }
    defaults.update(overrides)
    return ChatMessage(**defaults)


def test_map_text_message_to_chat_message_event() -> None:
    msg = _text_message()
    event = map_chat_message(msg, "skymiku39")
    assert event is not None
    assert event.platform == "twitch"
    assert event.topic == TOPIC_CHAT_MESSAGE
    assert event.message_id == "msg-001"
    assert event.author_name == "Viewer"
    assert event.author_id == "999"
    assert event.content == "hello world"
    assert event.channel == "skymiku39"
    assert event.raw["message_type"] == "textMessage"
    assert len(event.badges) == 2


def test_map_usernotice_sub() -> None:
    msg = _text_message(
        message_id="sub-001",
        message="User subscribed!",
        message_type="sub",
        amount="Tier 1",
        raw={"msg-id": "sub", "system-msg": "User subscribed!"},
    )
    event = map_chat_message(msg, "skymiku39")
    assert event is not None
    assert event.content == "User subscribed!"
    assert event.raw["message_type"] == "sub"
    assert event.raw["amount"] == "Tier 1"


def test_map_usernotice_raid() -> None:
    msg = _text_message(
        message_id="",
        message="Raider raided with 50 viewers",
        message_type="raid",
        raw={"msg-id": "raid"},
    )
    event = map_chat_message(msg, "skymiku39")
    assert event is not None
    assert event.message_id.startswith("irc-")
    assert event.raw["message_type"] == "raid"


def test_map_usernotice_bits() -> None:
    msg = _text_message(
        message_id="bits-001",
        message="Cheer100",
        message_type="bitsbadgetier",
        bits=100,
        amount="100 bits",
        raw={"msg-id": "bitsbadgetier", "bits": "100"},
    )
    event = map_chat_message(msg, "skymiku39")
    assert event is not None
    assert event.raw["message_type"] == "bitsbadgetier"
    assert event.raw["bits"] == 100
    assert event.raw["amount"] == "100 bits"


def test_skip_system_messages() -> None:
    for message_type in ("joined", "disconnected", "error", "notice", "reconnect"):
        msg = _text_message(message="system", message_type=message_type)
        assert should_publish(msg) is False
        assert map_chat_message(msg, "skymiku39") is None


def test_output_json_round_trip() -> None:
    event = map_chat_message(_text_message(), "skymiku39")
    assert event is not None
    restored = ChatMessageEvent.from_json(json.dumps(event.to_dict(), ensure_ascii=False))
    assert restored.message_id == event.message_id
    assert restored.content == event.content
    assert restored.raw["message_type"] == "textMessage"


def test_empty_content_not_published() -> None:
    msg = _text_message(message="   ")
    assert map_chat_message(msg, "skymiku39") is None


def test_missing_message_id_generates_fallback() -> None:
    msg = _text_message(message_id="", message="hi")
    event = map_chat_message(msg, "skymiku39")
    assert event is not None
    assert event.message_id.startswith("irc-")


def test_empty_author_name_falls_back_to_anonymous() -> None:
    msg = _text_message(author_name="")
    event = map_chat_message(msg, "skymiku39")
    assert event is not None
    assert event.author_name == "anonymous"
