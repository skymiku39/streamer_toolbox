import pytest

from events import TOPIC_CHARACTER_EXPRESSION_READY, TOPIC_CHARACTER_TURN

from sub_character_face.driver import VtsExpressionDriver
from sub_character_face.face import CharacterFace


def _sample_turn_payload() -> dict:
    return {
        "schema_version": 1,
        "topic": TOPIC_CHARACTER_TURN,
        "turn_id": "turn-abc",
        "correlation_id": "msg-xyz",
        "text": "角色要說的話",
        "emotion": "happy",
        "emotion_intensity": 0.8,
        "language": "zh-TW",
        "timestamp": "2026-06-12T17:00:00+08:00",
    }


def test_handle_publishes_expression_ready_with_turn_id() -> None:
    published: list[tuple[str, dict]] = []

    def publish(topic: str, payload: dict) -> None:
        published.append((topic, payload))

    face = CharacterFace(driver=VtsExpressionDriver(), publish=publish)
    face.handle(_sample_turn_payload())

    assert len(published) == 1
    topic, payload = published[0]
    assert topic == TOPIC_CHARACTER_EXPRESSION_READY
    assert payload["turn_id"] == "turn-abc"
    assert payload["driver"] == "vts"
    assert payload["parameters"]["mouth_smile"] == pytest.approx(0.72)
