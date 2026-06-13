import pytest

from events import TOPIC_CHARACTER_AUDIO_READY, TOPIC_CHARACTER_TURN, CharacterTurnEvent
from tts import SynthesizedAudio

from sub_character_voice.voice import CharacterVoiceSubscriber


class StubSynthesizer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def synthesize(self, text: str, *, turn_id: str, language: str = "zh-TW") -> SynthesizedAudio:
        self.calls.append((text, turn_id, language))
        return SynthesizedAudio(
            path=f"/tmp/{turn_id}.wav",
            duration_ms=1500,
            visemes=({"t": 0, "v": "aa"},),
        )


def _turn_payload() -> dict:
    return {
        "schema_version": 1,
        "topic": TOPIC_CHARACTER_TURN,
        "turn_id": "turn-001",
        "correlation_id": "msg-001",
        "text": "大家好！",
        "emotion": "happy",
        "emotion_intensity": 0.8,
        "language": "zh-TW",
        "timestamp": "2026-06-12T17:00:00+08:00",
    }


def test_handle_publishes_character_audio_ready() -> None:
    published: list[tuple[str, dict]] = []
    synthesizer = StubSynthesizer()
    subscriber = CharacterVoiceSubscriber(
        synthesizer=synthesizer,
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    subscriber.handle(_turn_payload())

    assert len(published) == 1
    topic, payload = published[0]
    assert topic == TOPIC_CHARACTER_AUDIO_READY
    assert payload["turn_id"] == "turn-001"
    assert payload["audio_path"] == "/tmp/turn-001.wav"
    assert payload["duration_ms"] == 1500
    assert payload["visemes"] == [{"t": 0, "v": "aa"}]
    assert synthesizer.calls == [("大家好！", "turn-001", "zh-TW")]


def test_handle_defaults_language_when_missing() -> None:
    published: list[tuple[str, dict]] = []
    synthesizer = StubSynthesizer()
    subscriber = CharacterVoiceSubscriber(
        synthesizer=synthesizer,
        publish=lambda topic, payload: published.append((topic, payload)),
    )

    payload = _turn_payload()
    payload["language"] = None
    subscriber.handle(payload)

    assert synthesizer.calls[0][2] == "zh-TW"


def test_handle_rejects_invalid_turn() -> None:
    subscriber = CharacterVoiceSubscriber(
        synthesizer=StubSynthesizer(),
        publish=lambda *_: None,
    )
    bad = _turn_payload()
    bad["emotion"] = "invalid"
    with pytest.raises(ValueError, match="emotion"):
        subscriber.handle(bad)
