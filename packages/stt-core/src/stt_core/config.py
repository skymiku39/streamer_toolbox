"""STT 設定：ingress（PCM 串流）與 voice-clone（離線去噪）共用。

denoise_* 欄位僅 voice-clone 路徑使用；ingress 不去噪，欄位保留預設即可。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return float(raw)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SttConfig:
    model_size: str
    chunk_seconds: float
    language: str
    device: str
    compute_type: str
    cpu_threads: int
    rms_gate: float
    filter_hallucinations: bool
    hallucination_rms_gate: float
    hallucination_speech_band_min: float
    hallucination_spectral_flatness_max: float
    vad_filter: bool
    condition_on_previous_text: bool
    no_speech_threshold: float
    log_prob_threshold: float
    compression_ratio_threshold: float
    beam_size: int = 1
    initial_prompt: str = ""
    carry_prompt: bool = True
    denoise_enabled: bool = True
    denoise_hp_cutoff_hz: float = 80.0
    denoise_gate_ratio: float = 0.08

    @classmethod
    def from_env(cls) -> SttConfig:
        return cls(
            model_size=os.environ.get("STT_MODEL_SIZE", "medium"),
            chunk_seconds=_env_float("STT_CHUNK_SECONDS", 4.0),
            language=os.environ.get("STT_LANGUAGE", "zh"),
            device=os.environ.get("STT_DEVICE", "auto"),
            compute_type=os.environ.get("STT_COMPUTE_TYPE", "auto"),
            cpu_threads=int(os.environ.get("STT_CPU_THREADS", "4")),
            rms_gate=_env_float("STT_RMS_GATE", 0.004),
            filter_hallucinations=_env_bool("STT_FILTER_HALLUCINATIONS", True),
            hallucination_rms_gate=_env_float("STT_HALLUCINATION_RMS_GATE", 0.02),
            hallucination_speech_band_min=_env_float("STT_HALLUCINATION_SPEECH_BAND_MIN", 0.25),
            hallucination_spectral_flatness_max=_env_float(
                "STT_HALLUCINATION_SPECTRAL_FLATNESS_MAX",
                0.35,
            ),
            vad_filter=_env_bool("STT_VAD_FILTER", False),
            condition_on_previous_text=_env_bool("STT_CONDITION_ON_PREVIOUS_TEXT", True),
            no_speech_threshold=_env_float("STT_NO_SPEECH_THRESHOLD", 0.85),
            log_prob_threshold=_env_float("STT_LOG_PROB_THRESHOLD", -1.0),
            compression_ratio_threshold=_env_float("STT_COMPRESSION_RATIO_THRESHOLD", 2.4),
            beam_size=int(os.environ.get("STT_BEAM_SIZE", "1")),
            initial_prompt=os.environ.get("STT_INITIAL_PROMPT", "").strip(),
            carry_prompt=_env_bool("STT_CARRY_PROMPT", True),
            denoise_enabled=_env_bool("STT_DENOISE", True),
            denoise_hp_cutoff_hz=_env_float("STT_DENOISE_HP_HZ", 80.0),
            denoise_gate_ratio=_env_float("STT_DENOISE_GATE_RATIO", 0.08),
        )
