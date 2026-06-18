"""faster-whisper 轉寫 worker（離線：去噪 + 重採樣 float32 路徑）。"""

from __future__ import annotations

import numpy as np
from scipy.signal import resample_poly

from stt_core import BaseSTTWorker, TranscriptSegment, pcm_to_float32
from voice_clone.stt.denoise import suppress_noise_for_stt

STT_SAMPLE_RATE = 16000


def _to_stt_audio(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    mono = audio.astype(np.float32)
    if mono.ndim > 1:
        mono = mono.mean(axis=1)
    if sample_rate != STT_SAMPLE_RATE:
        mono = resample_poly(mono, STT_SAMPLE_RATE, sample_rate).astype(np.float32)
    return mono


class STTWorker(BaseSTTWorker):
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
            segments, _info = model.transcribe(
                stt_audio,
                language=self._config.language or None,
                vad_filter=self._config.vad_filter,
                beam_size=1,
                condition_on_previous_text=self._config.condition_on_previous_text,
                no_speech_threshold=self._config.no_speech_threshold,
                log_prob_threshold=self._config.log_prob_threshold,
                compression_ratio_threshold=self._config.compression_ratio_threshold,
                temperature=0.0,
            )
            texts: list[str] = []
            apply_hallucination_filter = (
                self._input_filter.should_apply_hallucination_filter_audio(stt_audio)
            )
            for seg in segments:
                if apply_hallucination_filter and not self._input_filter.accept_segment(
                    seg,
                ):
                    continue
                text = (seg.text or "").strip()
                if not text:
                    continue
                if apply_hallucination_filter and not self._input_filter.accept_text(text):
                    continue
                texts.append(text)
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
                confidence=0.0,
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
