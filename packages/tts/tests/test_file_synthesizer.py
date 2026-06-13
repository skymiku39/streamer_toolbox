import pytest

from tts.file_synthesizer import FileVoiceSynthesizer, estimate_duration_ms


def test_estimate_duration_ms_minimum() -> None:
    assert estimate_duration_ms("") == 500


def test_estimate_duration_ms_scales_with_text() -> None:
    assert estimate_duration_ms("abcd") == 500
    assert estimate_duration_ms("a" * 10) == 1200


def test_file_synthesizer_writes_wav(tmp_path) -> None:
    synthesizer = FileVoiceSynthesizer(tmp_path)
    result = synthesizer.synthesize("測試", turn_id="turn-x", language="zh-TW")

    assert result.duration_ms == estimate_duration_ms("測試")
    assert result.path.endswith("turn-x.wav")
    assert (tmp_path / "turn-x.wav").is_file()
