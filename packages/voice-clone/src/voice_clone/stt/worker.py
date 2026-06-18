"""faster-whisper 轉寫 worker（離線：去噪 + 重採樣 float32 路徑）。"""

from __future__ import annotations

import numpy as np
from scipy.signal import resample_poly

from stt_core import BaseSTTWorker, TranscriptSegment, pcm_to_float32
from stt_core.denoise import suppress_noise_for_stt
from stt_core.transcribe_helpers import (
    build_whisper_kwargs,
    collect_whisper_texts,
    merge_confidence,
    resolve_initial_prompt,
)

STT_SAMPLE_RATE = 16000


def _to_stt_audio(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    mono = audio.astype(np.float32)
    if mono.ndim > 1:
        mono = mono.mean(axis=1)
    if sample_rate != STT_SAMPLE_RATE:
        mono = resample_poly(mono, STT_SAMPLE_RATE, sample_rate).astype(np.float32)
    return mono


class OfflineSTTWorker(BaseSTTWorker):
    def transcribe_audio(
        self,
        audio: np.ndarray,
        sample_rate: int,
        *,
        start_sec: float = 0.0,
    ) -> TranscriptSegment | None:
        stt_audio = _to_stt_audio(audio, sample_rate)
        if self._config.denoise_enabled:
            stt_audio = suppress_noise_for_stt(
                stt_audio,
                STT_SAMPLE_RATE,
                hp_cutoff_hz=self._config.denoise_hp_cutoff_hz,
                gate_ratio=self._config.denoise_gate_ratio,
            )
        if stt_audio.size == 0 or self._input_filter.is_silent_audio(stt_audio):
            return None

        try:
            model = self._ensure_model()
            prompt = resolve_initial_prompt(self._config)
            segments, _info = model.transcribe(
                stt_audio,
                **build_whisper_kwargs(self._config, initial_prompt=prompt),
            )
            apply_hallucination_filter = (
                self._input_filter.should_apply_hallucination_filter_audio(stt_audio)
            )
            texts, confidences = collect_whisper_texts(
                segments,
                self._input_filter,
                apply_hallucination_filter=apply_hallucination_filter,
            )
            if not texts:
                return None

            merged = " ".join(texts)
            if apply_hallucination_filter and not self._input_filter.accept_text(merged):
                return None
            duration = len(stt_audio) / STT_SAMPLE_RATE
            out = TranscriptSegment(
                text=merged,
                start_sec=start_sec,
                end_sec=start_sec + duration,
                confidence=merge_confidence(confidences),
            )
            if self._on_segment:
                self._on_segment(out)
            return out
        except Exception as exc:
            self._emit_error(f"STT 失敗: {exc}")
            return None

    def transcribe_chunk(
        self, pcm: bytes, *, stream_offset: float = 0.0
    ) -> TranscriptSegment | None:
        if self._input_filter.is_silent(pcm):
            return None
        audio = pcm_to_float32(pcm)
        return self.transcribe_audio(
            audio,
            STT_SAMPLE_RATE,
            start_sec=stream_offset,
        )
