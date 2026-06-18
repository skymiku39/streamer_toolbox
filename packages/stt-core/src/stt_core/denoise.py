"""輕量 STT 前處理降噪（numpy only，供 ingress 串流使用）。"""

from __future__ import annotations

import numpy as np

STT_SAMPLE_RATE = 16000


def highpass_moving_average(
    audio: np.ndarray,
    sample_rate: int,
    cutoff_hz: float,
) -> np.ndarray:
    """以移動平均近似高通，無 scipy 依賴。"""
    if audio.size == 0 or cutoff_hz <= 0:
        return audio.astype(np.float32)
    window = max(1, int(sample_rate / cutoff_hz))
    kernel = np.ones(window, dtype=np.float64) / window
    mono = audio.astype(np.float64)
    low = np.convolve(mono, kernel, mode="same")
    return (mono - low).astype(np.float32)


def spectral_gate(
    audio: np.ndarray,
    sample_rate: int,
    *,
    frame_ms: float = 20.0,
    gate_ratio: float = 0.08,
    attenuation: float = 0.15,
) -> np.ndarray:
    if audio.size == 0:
        return audio
    frame = max(1, int(sample_rate * frame_ms / 1000.0))
    out = audio.astype(np.float32).copy()
    peak = float(np.max(np.abs(out)))
    if peak <= 1e-8:
        return out
    threshold = peak * gate_ratio
    for start in range(0, len(out), frame):
        chunk = out[start : start + frame]
        if chunk.size == 0:
            break
        if float(np.sqrt(np.mean(np.square(chunk)))) < threshold:
            out[start : start + chunk.size] *= attenuation
    return out


def suppress_noise_for_stt(
    audio: np.ndarray,
    sample_rate: int = STT_SAMPLE_RATE,
    *,
    hp_cutoff_hz: float = 80.0,
    gate_ratio: float = 0.08,
) -> np.ndarray:
    if audio.size == 0:
        return audio
    mono = audio.astype(np.float32)
    if mono.ndim > 1:
        mono = mono.mean(axis=1)
    filtered = highpass_moving_average(mono, sample_rate, hp_cutoff_hz)
    return spectral_gate(filtered, sample_rate, gate_ratio=gate_ratio)
