"""faster-whisper 模型生命週期共用核心。

提供背景預載、裝置解析、模型載入與 callback；實際轉寫邏輯（PCM 串流或離線去噪）
由各 ingress / voice-clone 的子類別實作。
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from safety import SttInputFilter, pcm_to_float32
from stt_core.config import SttConfig
from stt_core.segment import TranscriptSegment

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

__all__ = ["BaseSTTWorker", "pcm_to_float32"]


class BaseSTTWorker:
    """Whisper 模型生命週期；子類別實作 transcribe_* 方法。"""

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
            hallucination_rms_gate=config.hallucination_rms_gate,
            hallucination_speech_band_min=config.hallucination_speech_band_min,
            hallucination_spectral_flatness_max=config.hallucination_spectral_flatness_max,
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
        self._device = "cpu"

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

    def _emit_status(self, msg: str) -> None:
        logger.info("%s", msg)
        if self._on_status:
            self._on_status(msg)

    def _emit_error(self, msg: str) -> None:
        logger.error("%s", msg)
        if self._on_error:
            self._on_error(msg)
