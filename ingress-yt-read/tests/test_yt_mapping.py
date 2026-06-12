from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tubechat_lens.reader import ChatMessage

from ingress_yt_read.mapper import map_chat_message
from pkg_events import TOPIC_CHAT_MESSAGE, ChatMessageEvent


def _sample_message(**overrides: object) -> ChatMessage:
    base = {
        "message_id": "msg-abc123",
        "author_name": "觀眾暱稱",
        "author_id": "UCtest123",
        "message": "你好世界",
        "timestamp": datetime(2026, 6, 12, 9, 0, 0, tzinfo=UTC),
        "message_type": "textMessage",
    }
    base.update(overrides)
    return ChatMessage(**base)  # type: ignore[arg-type]


def test_text_message_maps_to_chat_message_event() -> None:
    message = _sample_message()
    event = map_chat_message(message, channel="dQw4w9WgXcQ")

    assert event.platform == "youtube"
    assert event.message_id == "msg-abc123"
    assert event.author_name == "觀眾暱稱"
    assert event.author_id == "UCtest123"
    assert event.content == "你好世界"
    assert event.channel == "dQw4w9WgXcQ"
    assert event.raw["message_type"] == "textMessage"
    assert event.raw["source"] == "youtube_live_chat"


def test_round_trip_json_from_fixture_dict() -> None:
    message = _sample_message()
    fixture = message.to_dict()
    restored = ChatMessage(
        message_id=fixture["message_id"],
        author_name=fixture["author_name"],
        author_id=fixture["author_id"],
        message=fixture["message"],
        timestamp=datetime.fromisoformat(fixture["timestamp"]),
        message_type=fixture["message_type"],
        is_member=fixture["is_member"],
        is_moderator=fixture["is_moderator"],
        is_owner=fixture["is_owner"],
        is_verified=fixture["is_verified"],
        amount=fixture["amount"],
    )

    event = map_chat_message(restored, channel="dQw4w9WgXcQ")
    payload = event.to_dict()
    round_tripped = ChatMessageEvent.from_json(event.to_json())

    assert payload["schema_version"] == 1
    assert payload["topic"] == TOPIC_CHAT_MESSAGE
    assert payload["platform"] == "youtube"
    assert round_tripped == event


def test_super_chat_includes_amount_in_raw_and_content() -> None:
    message = _sample_message(
        message="",
        message_type="superChat",
        amount="USD 5.00",
    )
    event = map_chat_message(message, channel="live1234567")

    assert event.content == "[Super Chat USD 5.00]"
    assert event.raw["message_type"] == "superChat"
    assert event.raw["amount"] == "USD 5.00"


def test_membership_item_uses_fallback_content() -> None:
    message = _sample_message(message="", message_type="membershipItem", is_member=True)
    event = map_chat_message(message, channel="live1234567")

    assert event.content == "[membership]"
    assert event.raw["message_type"] == "membershipItem"
    assert event.badges == [{"type": "member"}]


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ({"is_owner": True}, [{"type": "owner"}]),
        ({"is_moderator": True}, [{"type": "moderator"}]),
        ({"is_verified": True}, [{"type": "verified"}]),
    ],
)
def test_badges_from_author_flags(flags: dict[str, bool], expected: list[dict[str, str]]) -> None:
    message = _sample_message(**flags)
    event = map_chat_message(message, channel="vid12345678")
    assert event.badges == expected
