import struct

import numpy as np
import pytest

from safety import SttInputFilter, is_hallucination_text, pcm_rms


def _pcm_from_amplitude(amplitude: float, sample_count: int = 1600) -> bytes:
    value = int(amplitude * 32767)
    return struct.pack(f"<{sample_count}h", *([value] * sample_count))


def _pcm_from_sine(amplitude: float, sample_count: int = 16000, freq_hz: float = 440.0) -> bytes:
    t = np.arange(sample_count, dtype=np.float64) / 16000.0
    wave = (amplitude * np.sin(2.0 * np.pi * freq_hz * t)).astype(np.float32)
    samples = np.clip(wave * 32767.0, -32768, 32767).astype(np.int16)
    return struct.pack(f"<{sample_count}h", *samples.tolist())


def test_pcm_rms_silence() -> None:
    assert pcm_rms(b"") == 0.0
    assert pcm_rms(_pcm_from_amplitude(0.0)) == 0.0


def test_pcm_rms_loud() -> None:
    rms = pcm_rms(_pcm_from_amplitude(0.5))
    assert 0.4 < rms < 0.6


@pytest.mark.parametrize(
    "text",
    [
        "",
        "嗯",
        "thanks for watching",
        "https://example.com",
        "[music]",
    ],
)
def test_hallucination_text_rejected(text: str) -> None:
    assert is_hallucination_text(text) is True


def test_valid_speech_accepted() -> None:
    assert is_hallucination_text("今天天氣真好") is False


@pytest.mark.parametrize(
    "text",
    [
        "呵呵",
        "然後",
        "神人",
        "腦殘",
        "啊",
        "呃",
        "欸_",
        "根本神人",
    ],
)
def test_short_cjk_speech_not_rejected(text: str) -> None:
    assert is_hallucination_text(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "啊啊",
        "嗯嗯",
    ],
)
def test_repeated_filler_still_rejected(text: str) -> None:
    assert is_hallucination_text(text) is True


def test_stt_input_filter_silence_gate() -> None:
    gate = SttInputFilter(rms_gate=0.05)
    assert gate.is_silent(_pcm_from_amplitude(0.01)) is True
    assert gate.is_silent(_pcm_from_amplitude(0.2)) is False


def test_hallucination_filter_only_on_non_speech_chunks() -> None:
    gate = SttInputFilter(
        rms_gate=0.004,
        filter_hallucinations=True,
        hallucination_rms_gate=0.02,
        hallucination_speech_band_min=0.25,
        hallucination_spectral_flatness_max=0.35,
    )
    quiet_noise = _pcm_from_amplitude(0.008)
    loud = _pcm_from_sine(0.2)
    assert gate.should_apply_hallucination_filter(quiet_noise) is True
    assert gate.should_apply_hallucination_filter(loud) is False
