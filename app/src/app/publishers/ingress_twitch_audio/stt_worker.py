"""faster-whisper 增量轉寫。"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import numpy as np

from ingress_twitch_audio.config import SttConfig
from ingress_twitch_audio.segment import TranscriptSegment
from safety import SttInputFilter

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


def _pcm_to_float32(pcm: bytes) -> np.ndarray:
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


class STTWorker:
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
        self._config = config
        self._input_filter = input_filter or SttInputFilter(
            rms_gate=config.rms_gate,
            filter_hallucinations=config.filter_hallucinations,
            hallucination_rms_gate=config.hallucination_rms_gate,
            no_speech_threshold=config.no_speech_threshold,
            log_prob_threshold=config.log_prob_threshold,
        )
        self._on_segment = on_segment
        self._on_status = on_status
        self._on_error = on_error
        self._base_offset = base_offset_sec or (lambda: None)
        self._model_loader = model_loader
        self._model: WhisperModel | None = None
        self._lock = threading.Lock()
        self._load_thread: threading.Thread | None = None
        self._model_ready = threading.Event()
        self._load_failed = threading.Event()
        self._device = "cpu"
        self._stream_offset = 0.0
        self._chunk_seconds = config.chunk_seconds

    def preload_in_background(self) -> None:
        with self._lock:
            if self._model is not None:
                self._model_ready.set()
                return
            if self._load_thread is not None and self._load_thread.is_alive():
                return

        def _load() -> None:
            try:
                self._ensure_model()
            except Exception as exc:
                self._load_failed.set()
                self._emit_error(f"載入 Whisper 失敗: {exc}")

        self._load_thread = threading.Thread(
            target=_load,
            daemon=True,
            name="stt-model-load",
        )
        self._load_thread.start()

    def wait_until_ready(self, timeout: float | None = 120.0) -> bool:
        if self._model is not None:
            return True
        if self._load_failed.is_set():
            return False
        return self._model_ready.wait(timeout=timeout)

    def _resolve_device(self) -> tuple[str, str]:
        device = self._config.device
        compute = self._config.compute_type
        if device == "auto":
            device = "cuda"
            try:
                import torch

                if not torch.cuda.is_available():
                    device = "cpu"
            except ImportError:
                device = "cpu"
        if compute == "auto":
            compute = "float16" if device == "cuda" else "int8"
        return device, compute

    def _ensure_model(self) -> WhisperModel:
        with self._lock:
            if self._model is not None:
                self._model_ready.set()
                return self._model

            if self._model_loader is not None:
                self._model = self._model_loader()
                self._model_ready.set()
                return self._model

            from faster_whisper import WhisperModel

            device, compute = self._resolve_device()
            self._emit_status(
                f"載入 Whisper 模型 {self._config.model_size} ({device})...",
            )
            model_kwargs: dict[str, Any] = {
                "device": device,
                "compute_type": compute,
            }
            if device == "cpu":
                model_kwargs["cpu_threads"] = self._config.cpu_threads
            self._model = WhisperModel(self._config.model_size, **model_kwargs)
            self._emit_status("Whisper 模型已就緒")
            self._device = device
            self._model_ready.set()
            return self._model

    def reset_stream_offset(self, offset: float = 0.0) -> None:
        self._stream_offset = max(0.0, offset)

    def transcribe_chunk(self, pcm: bytes) -> TranscriptSegment | None:
        if self._input_filter.is_silent(pcm):
            self._stream_offset += self._chunk_seconds
            return None

        audio = _pcm_to_float32(pcm)
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

    def _emit_status(self, msg: str) -> None:
        logger.info("%s", msg)
        if self._on_status:
            self._on_status(msg)

    def _emit_error(self, msg: str) -> None:
        logger.error("%s", msg)
        if self._on_error:
            self._on_error(msg)
