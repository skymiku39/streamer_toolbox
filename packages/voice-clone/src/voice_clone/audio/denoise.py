from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfiltfilt


def highpass_filter(audio: np.ndarray, sample_rate: int, cutoff_hz: float) -> np.ndarray:
    if audio.size == 0 or cutoff_hz <= 0:
        return audio.astype(np.float32)
    nyquist = sample_rate / 2.0
    normalized = min(0.99, cutoff_hz / nyquist)
    sos = butter(2, normalized, btype="high", output="sos")
    return sosfiltfilt(sos, audio.astype(np.float64)).astype(np.float32)


def spectral_gate(
    audio: np.ndarray,
    sample_rate: int,
    *,
    frame_ms: float = 20.0,
    gate_ratio: float = 0.08,
    attenuation: float = 0.15,
) -> np.ndarray:
    """簡易頻譜門檻：抑制低能量帧的雜訊。"""
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


def suppress_noise(
    audio: np.ndarray,
    sample_rate: int,
    *,
    hp_cutoff_hz: float = 80.0,
    gate_ratio: float = 0.08,
    attenuation: float = 0.15,
) -> np.ndarray:
    """高通 + 能量門檻衰減，抑制底噪。"""
    if audio.size == 0:
        return audio
    mono = audio.astype(np.float32)
    if mono.ndim > 1:
        mono = mono.mean(axis=1)
    filtered = highpass_filter(mono, sample_rate, hp_cutoff_hz)
    gated = spectral_gate(
        filtered,
        sample_rate,
        gate_ratio=gate_ratio,
        attenuation=attenuation,
    )
    peak = float(np.max(np.abs(gated)))
    if peak > 1e-8:
        gated = gated * min(1.0, 0.95 / peak)
    return gated.astype(np.float32)


def suppress_noise_for_sample(
    audio: np.ndarray,
    sample_rate: int,
    *,
    hp_cutoff_hz: float = 100.0,
    gate_ratio: float = 0.12,
) -> np.ndarray:
    """樣本音檔前處理：略強於 STT 預設，針對錄音底噪。"""
    return suppress_noise(
        audio,
        sample_rate,
        hp_cutoff_hz=hp_cutoff_hz,
        gate_ratio=gate_ratio,
        attenuation=0.1,
    )


def suppress_noise_for_stt(
    audio: np.ndarray,
    sample_rate: int,
    *,
    hp_cutoff_hz: float = 80.0,
    gate_ratio: float = 0.08,
) -> np.ndarray:
    """STT 前雜訊抑制（相容舊介面）。"""
    return suppress_noise(
        audio,
        sample_rate,
        hp_cutoff_hz=hp_cutoff_hz,
        gate_ratio=gate_ratio,
        attenuation=0.15,
    )
