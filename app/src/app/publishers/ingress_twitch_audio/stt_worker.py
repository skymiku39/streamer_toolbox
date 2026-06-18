"""faster-whisper 增量轉寫（PCM 串流）。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from safety import SttInputFilter
from stt_core import BaseSTTWorker, SttConfig, TranscriptSegment, pcm_to_float32


class STTWorker(BaseSTTWorker):
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

    def reset_stream_offset(self, offset: float = 0.0) -> None:
        self._stream_offset = max(0.0, offset)

    def transcribe_chunk(self, pcm: bytes) -> TranscriptSegment | None:
        if self._input_filter.is_silent(pcm):
            self._stream_offset += self._chunk_seconds
            return None

        audio = pcm_to_float32(pcm)
        if audio.size == 0:
            return None

        try:
            model = self._ensure_model()
            segments, _info = model.transcribe(
                audio,
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
            apply_hallucination_filter = self._input_filter.should_apply_hallucination_filter(
                pcm,
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
                self._stream_offset += self._chunk_seconds
                return None

            base = self._base_offset() or 0.0
            start = base + self._stream_offset
            end = start + self._chunk_seconds
            self._stream_offset += self._chunk_seconds
            merged = " ".join(texts)
            if apply_hallucination_filter and not self._input_filter.accept_text(merged):
                return None
            out = TranscriptSegment(text=merged, start_sec=start, end_sec=end, confidence=0.0)
            if self._on_segment:
                self._on_segment(out)
            return out
        except Exception as exc:
            self._emit_error(f"STT 失敗: {exc}")
            self._stream_offset += self._chunk_seconds
            return None
