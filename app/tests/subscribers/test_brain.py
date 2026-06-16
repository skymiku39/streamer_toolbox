from __future__ import annotations

from typing import Any

from events import TOPIC_CHARACTER_TURN, TOPIC_CHAT_REPLY

from safety import BlocklistSafetyFilter, PassThroughSafetyFilter
from sub_character_brain.brain import CharacterBrain
from sub_character_brain.config import CharacterConfig
from sub_character_brain.llm import CharacterResponse, RuleBasedCharacterLlm


class FixedLlm:
    def generate(self, **kwargs: Any) -> CharacterResponse:
        return CharacterResponse(
            text="角色回應測試",
            emotion="happy",
            emotion_intensity=0.9,
        )


def _chat_payload(content: str = "!talk 你好") -> dict:
    return {
        "schema_version": 1,
        "topic": "chat.message",
        "platform": "twitch",
        "message_id": "msg-001",
        "author_name": "觀眾A",
        "content": content,
        "timestamp": "2026-06-12T17:00:00+08:00",
        "channel": "test_channel",
        "badges": [],
        "emote_url_map": {},
        "reply": None,
        "raw": {},
    }


def test_chat_message_produces_character_turn() -> None:
    published: list[tuple[str, dict]] = []
    config = CharacterConfig(trigger_prefix="!talk", publish_chat_reply=False)
    brain = CharacterBrain(
        config=config,
        llm=FixedLlm(),
        safety=PassThroughSafetyFilter(),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    brain.handle(_chat_payload())

    assert len(published) == 1
    topic, payload = published[0]
    assert topic == TOPIC_CHARACTER_TURN
    assert payload["topic"] == TOPIC_CHARACTER_TURN
    assert payload["correlation_id"] == "msg-001"
    assert payload["text"] == "角色回應測試"
    assert payload["emotion"] == "happy"
    assert payload["turn_id"]


def test_optional_chat_reply() -> None:
    published: list[tuple[str, dict]] = []
    config = CharacterConfig(trigger_prefix="!talk", publish_chat_reply=True)
    brain = CharacterBrain(
        config=config,
        llm=FixedLlm(),
        safety=PassThroughSafetyFilter(),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    brain.handle(_chat_payload())

    assert len(published) == 2
    turn_topic, turn_payload = published[0]
    reply_topic, reply_payload = published[1]
    assert turn_topic == TOPIC_CHARACTER_TURN
    assert reply_topic == TOPIC_CHAT_REPLY
    assert reply_payload["source"] == "character-brain"
    assert reply_payload["correlation_id"] == "msg-001"
    assert reply_payload["channel"] == "test_channel"


def test_trigger_prefix_filters_messages() -> None:
    published: list[tuple[str, dict]] = []
    config = CharacterConfig(trigger_prefix="!talk", publish_chat_reply=False)
    brain = CharacterBrain(
        config=config,
        llm=FixedLlm(),
        safety=PassThroughSafetyFilter(),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    brain.handle(_chat_payload("一般聊天"))
    assert published == []


def test_safety_blocks_input() -> None:
    published: list[tuple[str, dict]] = []
    config = CharacterConfig(trigger_prefix="!talk", publish_chat_reply=False)
    brain = CharacterBrain(
        config=config,
        llm=FixedLlm(),
        safety=BlocklistSafetyFilter(blocklist=frozenset({"spam"})),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    brain.handle(_chat_payload("!talk spam here"))
    assert published == []


def test_character_turn_round_trip() -> None:
    published: list[tuple[str, dict]] = []
    config = CharacterConfig(trigger_prefix="!talk", publish_chat_reply=False)
    brain = CharacterBrain(
        config=config,
        llm=RuleBasedCharacterLlm(),
        safety=PassThroughSafetyFilter(),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    brain.handle(_chat_payload("!talk 我很開心"))
    _, payload = published[0]
    from events import CharacterTurnEvent

    event = CharacterTurnEvent.from_dict(payload)
    assert event.emotion == "happy"
    assert "觀眾A" in event.text


def test_respond_to_all_mode() -> None:
    published: list[tuple[str, dict]] = []
    config = CharacterConfig(respond_to_all=True, publish_chat_reply=False)
    brain = CharacterBrain(
        config=config,
        llm=FixedLlm(),
        safety=PassThroughSafetyFilter(),
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    brain.handle(_chat_payload("隨便聊聊"))
    assert len(published) == 1
