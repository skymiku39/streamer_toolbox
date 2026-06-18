"""PCM 頻譜特徵（對齊 packages/safety/audio_spectrum）。"""

from __future__ import annotations

import numpy as np

STT_SAMPLE_RATE = 16000
_SPEECH_BAND_LOW_HZ = 200.0
_SPEECH_BAND_HIGH_HZ = 4000.0


def pcm_to_float32(pcm: bytes) -> np.ndarray:
    if len(pcm) < 2:
        return np.array([], dtype=np.float32)
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


def float32_rms(audio: np.ndarray) -> float:
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio.astype(np.float64)))))


def speech_band_energy_ratio(
    audio: np.ndarray,
    sample_rate: int = STT_SAMPLE_RATE,
    *,
    low_hz: float = _SPEECH_BAND_LOW_HZ,
    high_hz: float = _SPEECH_BAND_HIGH_HZ,
) -> float:
    if audio.size == 0:
        return 0.0
    spectrum = np.abs(np.fft.rfft(audio)) ** 2
    freqs = np.fft.rfftfreq(audio.size, 1.0 / sample_rate)
    total = float(spectrum[1:].sum())
    if total <= 0.0:
        return 0.0
    mask = (freqs >= low_hz) & (freqs <= high_hz)
    return float(spectrum[mask].sum() / total)


def spectral_flatness(audio: np.ndarray) -> float:
    if audio.size == 0:
        return 1.0
    spectrum = np.abs(np.fft.rfft(audio)) ** 2
    spectrum = spectrum[1:]
    if spectrum.size == 0:
        return 1.0
    spectrum = np.maximum(spectrum, 1e-12)
    geometric = float(np.exp(np.mean(np.log(spectrum))))
    arithmetic = float(np.mean(spectrum))
    if arithmetic <= 0.0:
        return 1.0
    return geometric / arithmetic


def lacks_clear_speech(
    pcm: bytes,
    *,
    sample_rate: int = STT_SAMPLE_RATE,
    rms_gate: float = 0.02,
    max_spectral_flatness: float = 0.35,
    min_speech_band_ratio: float = 0.25,
) -> bool:
    audio = pcm_to_float32(pcm)
    if audio.size == 0:
        return True
    rms = float32_rms(audio)
    if rms < rms_gate:
        return True
    if spectral_flatness(audio) > max_spectral_flatness:
        return True
    return speech_band_energy_ratio(audio, sample_rate) < min_speech_band_ratio


def lacks_clear_speech_audio(
    audio: np.ndarray,
    *,
    sample_rate: int = STT_SAMPLE_RATE,
    rms_gate: float = 0.02,
    max_spectral_flatness: float = 0.35,
    min_speech_band_ratio: float = 0.25,
) -> bool:
    if audio.size == 0:
        return True
    rms = float32_rms(audio)
    if rms < rms_gate:
        return True
    if spectral_flatness(audio) > max_spectral_flatness:
        return True
    return speech_band_energy_ratio(audio, sample_rate) < min_speech_band_ratio
