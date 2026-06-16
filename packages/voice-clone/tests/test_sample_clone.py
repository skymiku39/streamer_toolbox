from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from voice_clone.config import Settings
from voice_clone.inference.checkpoints import resolve_model_bundle
from voice_clone.inference.sample_ref import resolve_sample_reference
from voice_clone.stt.segment import TranscriptSegment


def test_resolve_model_bundle_default_name(tmp_path: Path) -> None:
    settings = Settings(VOICE_CLONE_ROOT=tmp_path)
    bundle = resolve_model_bundle(settings=settings)
    assert "OmniVoice" in bundle.model_id


def test_resolve_sample_reference_with_text(tmp_path: Path) -> None:
    sample = tmp_path / "sample.wav"
    sample.write_bytes(b"RIFF")
    ref = resolve_sample_reference(sample, sample_text="各位觀眾大家好")
    assert ref.audio_path == sample.resolve()
    assert ref.text == "各位觀眾大家好"


def test_resolve_sample_reference_with_stt(tmp_path: Path) -> None:
    sample = tmp_path / "sample.wav"
    duration = 0.5
    sample_rate = 32000
    audio = np.zeros(int(duration * sample_rate), dtype=np.float32)
    import soundfile as sf

    sf.write(sample, audio, sample_rate)

    worker = MagicMock()
    worker.transcribe_audio.return_value = TranscriptSegment(
        text="這是樣本轉寫文字",
        start_sec=0.0,
        end_sec=duration,
    )
    ref = resolve_sample_reference(sample, stt_worker=worker)
    assert ref.text == "這是樣本轉寫文字"
    worker.transcribe_audio.assert_called_once()


def test_resolve_sample_reference_from_paired_text(tmp_path: Path) -> None:
    audio_dir = tmp_path / "streamer" / "audio"
    text_dir = tmp_path / "streamer" / "text"
    audio_dir.mkdir(parents=True)
    text_dir.mkdir(parents=True)
    sample = audio_dir / "001.wav"
    sample.write_bytes(b"RIFF")
    (text_dir / "001.txt").write_text("各位觀眾大家好，歡迎來到我的直播間。", encoding="utf-8")

    ref = resolve_sample_reference(sample)
    assert ref.text == "各位觀眾大家好，歡迎來到我的直播間。"


def test_resolve_sample_reference_requires_text_or_stt(tmp_path: Path) -> None:
    sample = tmp_path / "sample.wav"
    sample.write_bytes(b"RIFF")
    with pytest.raises(ValueError, match="sample-text"):
        resolve_sample_reference(sample)
