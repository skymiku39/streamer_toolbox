"""faster-whisper 轉寫 worker（移植自 streamer_toolbox ingress STTWorker）。"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import numpy as np
from scipy.signal import resample_poly

from voice_clone.stt.config import SttConfig
from voice_clone.stt.denoise import suppress_noise_for_stt
from voice_clone.stt.filter import SttInputFilter
from voice_clone.stt.segment import TranscriptSegment

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

STT_SAMPLE_RATE = 16000


def _pcm_to_float32(pcm: bytes) -> np.ndarray:
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


def _to_stt_audio(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    mono = audio.astype(np.float32)
    if mono.ndim > 1:
        mono = mono.mean(axis=1)
    if sample_rate != STT_SAMPLE_RATE:
        mono = resample_poly(mono, STT_SAMPLE_RATE, sample_rate).astype(np.float32)
    return mono


class STTWorker:
    def __init__(
        self,
        config: SttConfig,
        *,
        input_filter: SttInputFilter | None = None,
        on_segment: Callable[[TranscriptSegment], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        model_loader: Callable[[], Any] | None = None,
    ) -> None:
        self._config = config
        self._input_filter = input_filter or SttInputFilter(
            rms_gate=config.rms_gate,
            filter_hallucinations=config.filter_hallucinations,
            no_speech_threshold=config.no_speech_threshold,
            log_prob_threshold=config.log_prob_threshold,
        )
        self._on_segment = on_segment
        self._on_status = on_status
        self._on_error = on_error
        self._model_loader = model_loader
        self._model: WhisperModel | None = None
        self._lock = threading.Lock()
        self._load_thread: threading.Thread | None = None
        self._model_ready = threading.Event()
        self._load_failed = threading.Event()

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
            self._model_ready.set()
            return self._model

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
            for seg in segments:
                if (
                    self._config.filter_hallucinations
                    and not self._input_filter.accept_segment(seg)
                ):
                    continue
                text = (seg.text or "").strip()
                if text and self._input_filter.accept_text(text):
                    texts.append(text)
            if not texts:
                return None

            merged = " ".join(texts)
            if not self._input_filter.accept_text(merged):
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
        if self._input_filter.is_silent_pcm(pcm):
            return None
        audio = _pcm_to_float32(pcm)
        segment = self.transcribe_audio(
            audio,
            STT_SAMPLE_RATE,
            start_sec=stream_offset,
        )
        return segment

    def _emit_status(self, msg: str) -> None:
        logger.info("%s", msg)
        if self._on_status:
            self._on_status(msg)

    def _emit_error(self, msg: str) -> None:
        logger.error("%s", msg)
        if self._on_error:
            self._on_error(msg)
