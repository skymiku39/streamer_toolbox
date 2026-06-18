"""PCM 串流增量轉寫 worker（faster-whisper）。

供各 ingress（Twitch 直播音訊、本機麥克風等）共用：以固定長度 PCM chunk
逐段轉寫，並維護串流時間 offset。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from safety import SttInputFilter
from stt_core.config import SttConfig
from stt_core.denoise import suppress_noise_for_stt
from stt_core.segment import TranscriptSegment
from stt_core.transcribe_helpers import (
    build_whisper_kwargs,
    collect_whisper_texts,
    merge_confidence,
    resolve_initial_prompt,
)
from stt_core.worker import BaseSTTWorker, pcm_to_float32

STT_SAMPLE_RATE = 16000


class StreamingSTTWorker(BaseSTTWorker):
    def __init__(
        self,
        config: SttConfig,
        *,
        input_filter: SttInputFilter | None = None,
        on_segment: Callable[[TranscriptSegment], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        base_offset_sec: Callable[[], float | None] | None = None,
        model_loader: Callable[[], Any] | None = None,
    ) -> None:
        super().__init__(
            config,
            input_filter=input_filter,
            on_segment=on_segment,
            on_status=on_status,
            on_error=on_error,
            model_loader=model_loader,
        )
        self._base_offset = base_offset_sec or (lambda: None)
        self._stream_offset = 0.0
        self._chunk_seconds = config.chunk_seconds
        self._last_transcript = ""

    def reset_stream_offset(self, offset: float = 0.0) -> None:
        self._stream_offset = max(0.0, offset)
        self._last_transcript = ""

    def _prepare_audio(self, pcm: bytes) -> np.ndarray:
        audio = pcm_to_float32(pcm)
        if audio.size == 0:
            return audio
        if self._config.denoise_enabled:
            audio = suppress_noise_for_stt(
                audio,
                STT_SAMPLE_RATE,
                hp_cutoff_hz=self._config.denoise_hp_cutoff_hz,
                gate_ratio=self._config.denoise_gate_ratio,
            )
        return audio

    def transcribe_chunk(self, pcm: bytes) -> TranscriptSegment | None:
        if self._input_filter.is_silent(pcm):
            self._stream_offset += self._chunk_seconds
            return None

        audio = self._prepare_audio(pcm)
        if audio.size == 0:
            return None

        try:
            model = self._ensure_model()
            prompt = resolve_initial_prompt(
                self._config,
                last_text=self._last_transcript,
            )
            segments, _info = model.transcribe(
                audio,
                **build_whisper_kwargs(self._config, initial_prompt=prompt),
            )
            apply_hallucination_filter = self._input_filter.should_apply_hallucination_filter(
                pcm,
            )
            texts, confidences = collect_whisper_texts(
                segments,
                self._input_filter,
                apply_hallucination_filter=apply_hallucination_filter,
            )
            if not texts:
                self._stream_offset += self._chunk_seconds
                return None

            base = self._base_offset() or 0.0
            start = base + self._stream_offset
            end = start + self._chunk_seconds
            self._stream_offset += self._chunk_seconds
            merged = " ".join(texts)
            if apply_hallucination_filter and not self._input_filter.accept_text(merged):
                return None
            confidence = merge_confidence(confidences)
            self._last_transcript = merged
            out = TranscriptSegment(
                text=merged,
                start_sec=start,
                end_sec=end,
                confidence=confidence,
            )
            if self._on_segment:
                self._on_segment(out)
            return out
        except Exception as exc:
            self._emit_error(f"STT 失敗: {exc}")
            self._stream_offset += self._chunk_seconds
            return None
