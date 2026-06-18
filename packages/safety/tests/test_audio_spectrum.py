import struct

import numpy as np

from safety.audio_spectrum import (
    lacks_clear_speech,
    speech_band_energy_ratio,
    spectral_flatness,
)


def _pcm_from_sine(amplitude: float, freq_hz: float = 440.0, sample_count: int = 16000) -> bytes:
    t = np.arange(sample_count, dtype=np.float64) / 16000.0
    wave = (amplitude * np.sin(2.0 * np.pi * freq_hz * t)).astype(np.float32)
    samples = np.clip(wave * 32767.0, -32768, 32767).astype(np.int16)
    return struct.pack(f"<{sample_count}h", *samples.tolist())


def test_speech_sine_has_high_band_ratio_and_low_flatness() -> None:
    pcm = _pcm_from_sine(0.2, freq_hz=440.0)
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    assert speech_band_energy_ratio(audio) > 0.9
    assert spectral_flatness(audio) < 0.05
    assert lacks_clear_speech(pcm) is False


def test_white_noise_lacks_clear_speech() -> None:
    noise = (np.random.default_rng(0).standard_normal(16000).astype(np.float32) * 0.01)
    pcm = struct.pack(f"<{16000}h", *np.clip(noise * 32767, -32768, 32767).astype(np.int16).tolist())
    assert lacks_clear_speech(pcm) is True
