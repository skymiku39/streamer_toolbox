from __future__ import annotationsimport sysimport threadingfrom collections.abc import Callablefrom typing import Anyfrom events import (    TOPIC_CHARACTER_AUDIO_READY,    CharacterAudioReadyEvent,    CharacterTurnEvent,)from tts import VoiceSynthesizerclass CharacterVoiceSubscriber:
    """訂閱 character.turn → TTS 合成 → 發布 character.audio.ready。"""

    def __init__(
        self,
        synthesizer: VoiceSynthesizer,
        publish: Callable[[str, dict[str, Any]], None],
    ) -> None:
        self._synthesizer = synthesizer
        self._publish = publish
        self._processed = 0
        self._lock = threading.Lock()

    def handle(self, payload: dict[str, Any]) -> None:
        turn = CharacterTurnEvent.from_dict(payload)
        language = turn.language or "zh-TW"
        audio = self._synthesizer.synthesize(
            turn.text,
            turn_id=turn.turn_id,
            language=language,
        )
        event = CharacterAudioReadyEvent(
            schema_version=1,
            topic=TOPIC_CHARACTER_AUDIO_READY,
            turn_id=turn.turn_id,
            audio_path=audio.path,
            duration_ms=audio.duration_ms,
            visemes=list(audio.visemes),
        )
        self._publish(TOPIC_CHARACTER_AUDIO_READY, event.to_dict())

        with self._lock:
            self._processed += 1

    def processed_count(self) -> int:
        with self._lock:
            return self._processed

    def log_stats(self) -> None:
        print(
            f"[stats] processed={self.processed_count()}",
            file=sys.stderr,
            flush=True,
        )
