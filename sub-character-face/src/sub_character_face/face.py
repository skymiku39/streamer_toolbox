from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pkg_events import (
    TOPIC_CHARACTER_EXPRESSION_READY,
    CharacterExpressionReadyEvent,
    CharacterTurnEvent,
)

from sub_character_face.driver import ExpressionDriver
from sub_character_face.mapper import map_emotion_to_parameters


class CharacterFace:
    """訂閱 character.turn，映射表情並發布 character.expression.ready。"""

    def __init__(
        self,
        driver: ExpressionDriver,
        publish: Callable[[str, dict[str, Any]], None],
    ) -> None:
        self._driver = driver
        self._publish = publish

    def handle(self, payload: dict[str, Any]) -> None:
        turn = CharacterTurnEvent.from_dict(payload)
        parameters = map_emotion_to_parameters(turn.emotion, turn.emotion_intensity)
        applied = self._driver.apply(parameters)
        ready = CharacterExpressionReadyEvent(
            schema_version=1,
            topic=TOPIC_CHARACTER_EXPRESSION_READY,
            turn_id=turn.turn_id,
            driver=self._driver.name,
            parameters=applied,
        )
        self._publish(TOPIC_CHARACTER_EXPRESSION_READY, ready.to_dict())
