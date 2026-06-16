from __future__ import annotations

from types import SimpleNamespace

import pytest
from events import TOPIC_CHAT_MESSAGE, eventsub_topic

from ingress_twitch_eventsub.normalize import (
    chat_message_from_eventsub,
    eventsub_from_follow,
    eventsub_from_raid,
)


def _chat_message_fixture() -> SimpleNamespace:
    badge = SimpleNamespace(set_id="subscriber", id="12")
    chatter = SimpleNamespace(
        id="user-1",
        name="viewer_login",
        display_name="觀眾暱稱",
        badges=[badge],
    )
    broadcaster = SimpleNamespace(id="broadcaster-1", name="channel_name")
    return SimpleNamespace(
        id="msg-123",
        text="hello world",
        timestamp="2026-06-12T17:00:00+08:00",
        chatter=chatter,
        broadcaster=broadcaster,
        fragments=[],
        reply=None,
        source_broadcaster=None,
    )


def test_chat_message_from_eventsub_maps_required_fields() -> None:
    event = chat_message_from_eventsub(_chat_message_fixture())
    payload = event.to_dict()
    assert payload["topic"] == TOPIC_CHAT_MESSAGE
    assert payload["platform"] == "twitch"
    assert payload["message_id"] == "msg-123"
    assert payload["author_name"] == "觀眾暱稱"
    assert payload["login"] == "viewer_login"
    assert payload["content"] == "hello world"
    assert payload["channel"] == "channel_name"
    assert payload["raw"]["source"] == "twitch_eventsub"


def test_eventsub_follow_maps_topic_and_payload() -> None:
    payload = SimpleNamespace(
        broadcaster=SimpleNamespace(id="broadcaster-1"),
        user=SimpleNamespace(id="user-1", name="viewer_login", display_name="觀眾暱稱"),
        followed_at="2026-06-12T17:00:00+08:00",
    )
    event = eventsub_from_follow(payload)
    assert event.topic == eventsub_topic("follow")
    assert event.event_type == "follow"
    assert event.broadcaster_id == "broadcaster-1"
    assert event.user_id == "user-1"
    assert event.payload["followed_at"] == "2026-06-12T17:00:00+08:00"


def test_eventsub_raid_maps_viewer_count() -> None:
    payload = SimpleNamespace(
        from_broadcaster=SimpleNamespace(id="raider-1", name="raider"),
        to_broadcaster=SimpleNamespace(id="broadcaster-1", name="channel_name"),
        viewer_count=42,
        created_at="2026-06-12T17:00:00+08:00",
    )
    event = eventsub_from_raid(payload)
    assert event.topic == eventsub_topic("raid")
    assert event.payload["viewer_count"] == 42


def test_chat_message_requires_content() -> None:
    message = _chat_message_fixture()
    message.text = ""
    with pytest.raises(ValueError, match="content"):
        chat_message_from_eventsub(message)
