from __future__ import annotations

import json
from pathlib import Path

import pytest

from pkg_events import (
    SOURCE_LOGIC_COMMANDS,
    SOURCE_LOGIC_EVENTS,
    SOURCE_LOGIC_KEYWORDS,
    TOPIC_CHAT_MESSAGE,
    ChatMessageEvent,
    EventSubEvent,
    eventsub_topic,
)
from sub_bot_logic.redemption_map import RedemptionResponseMap
from sub_bot_logic.response_map import BotResponseMap
from sub_bot_logic.rules_engine import BotRulesEngine

_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config" / "examples"


@pytest.fixture
def engine() -> BotRulesEngine:
    return BotRulesEngine(
        BotResponseMap(_CONFIG_DIR / "bot_responses.example.json"),
        RedemptionResponseMap(_CONFIG_DIR / "redemption_responses.example.json"),
        bot_identity="Test Bot",
    )


def _chat_message(**overrides) -> ChatMessageEvent:
    payload = {
        "schema_version": 1,
        "topic": TOPIC_CHAT_MESSAGE,
        "platform": "twitch",
        "message_id": "msg-001",
        "author_name": "Viewer",
        "login": "viewer",
        "content": "!hello",
        "timestamp": "2026-06-12T17:00:00+08:00",
        "channel": "testchannel",
        "badges": [],
        "raw": {"message_type": "textMessage"},
    }
    payload.update(overrides)
    return ChatMessageEvent.from_dict(payload)


def test_command_hello(engine: BotRulesEngine) -> None:
    reply = engine.process_chat_message(_chat_message(content="!hello"))
    assert reply is not None
    assert reply.source == SOURCE_LOGIC_COMMANDS
    assert reply.topic == "chat.reply"
    assert "Viewer" in reply.content
    assert reply.correlation_id == "msg-001"


def test_keyword_trigger(engine: BotRulesEngine) -> None:
    reply = engine.process_chat_message(_chat_message(content="大家安安好"))
    assert reply is not None
    assert reply.source == SOURCE_LOGIC_KEYWORDS
    assert "Viewer" in reply.content


def test_command_acl_denied(engine: BotRulesEngine) -> None:
    reply = engine.process_chat_message(
        _chat_message(content="!echo test", badges=[]),
    )
    assert reply is not None
    assert reply.source == SOURCE_LOGIC_COMMANDS
    assert "權限" in reply.content


def test_irc_sub_usernotice(engine: BotRulesEngine) -> None:
    message = _chat_message(
        content="User subscribed!",
        raw={"message_type": "sub", "amount": "Tier 1"},
    )
    reply = engine.process_chat_message(message)
    assert reply is not None
    assert reply.source == SOURCE_LOGIC_EVENTS
    assert "Viewer" in reply.content


def test_eventsub_follow(engine: BotRulesEngine) -> None:
    event = EventSubEvent.from_dict(
        {
            "schema_version": 1,
            "topic": eventsub_topic("follow"),
            "platform": "twitch",
            "event_type": "follow",
            "broadcaster_id": "123",
            "user_id": "456",
            "user_name": "new_follower",
            "timestamp": "2026-06-12T17:00:00+08:00",
            "channel": "testchannel",
            "payload": {},
        }
    )
    reply = engine.process_eventsub(event)
    assert reply is not None
    assert reply.source == SOURCE_LOGIC_EVENTS
    assert "new_follower" in reply.content
    assert reply.channel == "testchannel"


def test_eventsub_redemption(engine: BotRulesEngine) -> None:
    event = EventSubEvent.from_dict(
        {
            "schema_version": 1,
            "topic": eventsub_topic("redemption"),
            "platform": "twitch",
            "event_type": "redemption",
            "broadcaster_id": "123",
            "user_id": "456",
            "user_name": "viewer",
            "timestamp": "2026-06-12T17:00:00+08:00",
            "channel": "testchannel",
            "payload": {
                "reward_title": "加入歌曲",
                "reward_cost": 500,
                "user_input": "夜に駆ける",
            },
        }
    )
    reply = engine.process_eventsub(event)
    assert reply is not None
    assert "viewer" in reply.content
    assert "歌" in reply.content


def test_chat_reply_round_trip_via_engine(engine: BotRulesEngine) -> None:
    reply = engine.process_chat_message(_chat_message(content="!ping"))
    assert reply is not None
    restored = json.loads(reply.to_json())
    assert restored["source"] == SOURCE_LOGIC_COMMANDS
    assert restored["correlation_id"] == "msg-001"
