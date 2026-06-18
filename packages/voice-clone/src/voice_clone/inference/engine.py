from __future__ import annotations

from pathlib import Path

from bus import EventBus
from voice_clone.config import Settings, get_settings
from voice_clone.events.payloads import SynthesisCompletedPayload
from voice_clone.events.topics import TOPIC_SYNTHESIS_COMPLETED
from voice_clone.inference.checkpoints import ModelBundle
from voice_clone.inference.omnivoice_runner import OmniVoiceRunner


class InferenceEngine:
    def __init__(self, bus: EventBus | None = None, settings: Settings | None = None) -> None:
        self._bus = bus
        self._settings = settings or get_settings()
        self._runner = OmniVoiceRunner(self._settings)

    def synthesize(
        self,
        text: str,
        output_path: Path,
        *,
        bundle: ModelBundle,
        ref_audio: Path,
        ref_text: str | None,
        language: str | None = None,
        num_step: int | None = None,
    ) -> SynthesisCompletedPayload:
        result_path = self._runner.synthesize(
            model_id=bundle.model_id,
            ref_audio=ref_audio,
            ref_text=ref_text,
            target_text=text,
            output_path=output_path,
            language=language,
            num_step=num_step,
        )
        payload = SynthesisCompletedPayload(
            text=text,
            output_path=str(result_path),
            sample_rate=self._settings.target_sample_rate,
        )
        if self._bus is not None:
            self._bus.publish(TOPIC_SYNTHESIS_COMPLETED, payload.model_dump())
        return payload
