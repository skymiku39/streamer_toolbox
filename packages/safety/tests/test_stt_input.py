import struct

import pytest

from safety import SttInputFilter, is_hallucination_text, pcm_rms


def _pcm_from_amplitude(amplitude: float, sample_count: int = 1600) -> bytes:
    value = int(amplitude * 32767)
    return struct.pack(f"<{sample_count}h", *([value] * sample_count))


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


def test_stt_input_filter_silence_gate() -> None:
    gate = SttInputFilter(rms_gate=0.05)
    assert gate.is_silent(_pcm_from_amplitude(0.01)) is True
    assert gate.is_silent(_pcm_from_amplitude(0.2)) is False
