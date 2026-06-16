from __future__ import annotations

import threading
import time

import pytest
from events import (
    TOPIC_CHARACTER_AUDIO_READY,
    TOPIC_CHARACTER_EXPRESSION_READY,
    CharacterAudioReadyEvent,
    CharacterExpressionReadyEvent,
)

from sub_character_stage.coordinator import TurnCoordinator
from sub_character_stage.cue import StageCue


class RecordingDriver:
    def __init__(self) -> None:
        self.cues: list[StageCue] = []
        self._lock = threading.Lock()

    def play_turn(self, cue: StageCue) -> None:
        with self._lock:
            self.cues.append(cue)

    def close(self) -> None:
        return None


def _audio(turn_id: str = "turn-1") -> CharacterAudioReadyEvent:
    return CharacterAudioReadyEvent.from_dict(
        {
            "schema_version": 1,
            "topic": TOPIC_CHARACTER_AUDIO_READY,
            "turn_id": turn_id,
            "audio_path": "/tmp/voice.wav",
            "duration_ms": 1200,
            "visemes": [],
        }
    )


def _expression(turn_id: str = "turn-1") -> CharacterExpressionReadyEvent:
    return CharacterExpressionReadyEvent.from_dict(
        {
            "schema_version": 1,
            "topic": TOPIC_CHARACTER_EXPRESSION_READY,
            "turn_id": turn_id,
            "driver": "vts",
            "parameters": {"mouth_smile": 0.9},
        }
    )


def test_fires_when_both_ready() -> None:
    driver = RecordingDriver()
    coordinator = TurnCoordinator(driver, merge_timeout_sec=1.0)

    coordinator.handle_audio(_audio())
    coordinator.handle_expression(_expression())

    assert len(driver.cues) == 1
    cue = driver.cues[0]
    assert cue.turn_id == "turn-1"
    assert cue.expression is not None
    assert cue.expression_fallback is False


def test_expression_before_audio() -> None:
    driver = RecordingDriver()
    coordinator = TurnCoordinator(driver, merge_timeout_sec=1.0)

    coordinator.handle_expression(_expression())
    coordinator.handle_audio(_audio())

    assert len(driver.cues) == 1
    assert driver.cues[0].expression is not None
    assert driver.cues[0].expression_fallback is False


def test_audio_only_fallback_after_timeout() -> None:
    driver = RecordingDriver()
    coordinator = TurnCoordinator(driver, merge_timeout_sec=0.05)

    coordinator.handle_audio(_audio())
    time.sleep(0.12)

    assert len(driver.cues) == 1
    cue = driver.cues[0]
    assert cue.expression is None
    assert cue.expression_fallback is True


def test_ignores_late_events_after_fire() -> None:
    driver = RecordingDriver()
    coordinator = TurnCoordinator(driver, merge_timeout_sec=0.05)

    coordinator.handle_audio(_audio())
    time.sleep(0.12)
    coordinator.handle_expression(_expression())

    assert len(driver.cues) == 1


def test_expression_only_never_fires() -> None:
    driver = RecordingDriver()
    coordinator = TurnCoordinator(driver, merge_timeout_sec=0.05)

    coordinator.handle_expression(_expression())
    time.sleep(0.12)

    assert driver.cues == []


def test_separate_turn_ids() -> None:
    driver = RecordingDriver()
    coordinator = TurnCoordinator(driver, merge_timeout_sec=1.0)

    coordinator.handle_audio(_audio("turn-a"))
    coordinator.handle_audio(_audio("turn-b"))
    coordinator.handle_expression(_expression("turn-a"))
    coordinator.handle_expression(_expression("turn-b"))

    assert len(driver.cues) == 2
    turn_ids = {cue.turn_id for cue in driver.cues}
    assert turn_ids == {"turn-a", "turn-b"}


@pytest.mark.parametrize("merge_timeout_sec", [0.0, -1.0])
def test_invalid_merge_timeout_rejected_at_construction(merge_timeout_sec: float) -> None:
    driver = RecordingDriver()
    with pytest.raises(ValueError, match="merge_timeout_sec"):
        TurnCoordinator(driver, merge_timeout_sec=merge_timeout_sec)
