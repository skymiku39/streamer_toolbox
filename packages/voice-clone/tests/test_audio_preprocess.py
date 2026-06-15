import numpy as np

from voice_clone.audio.denoise import suppress_noise_for_sample
from voice_clone.audio.preprocess import preprocess_sample_audio
from voice_clone.audio.trim import trim_silence_edges


def test_suppress_noise_reduces_low_energy_frames() -> None:
    sr = 32000
    rng = np.random.default_rng(0)
    noise = rng.normal(0, 0.02, sr).astype(np.float32)
    speech = np.ones(sr, dtype=np.float32) * 0.35
    audio = np.concatenate([noise, speech, noise])
    cleaned = suppress_noise_for_sample(audio, sr)
    assert cleaned.size == audio.size
    assert float(np.max(np.abs(cleaned))) <= 1.0
    assert float(np.mean(np.abs(cleaned[: sr // 4]))) < float(np.mean(np.abs(noise)))


def test_trim_silence_edges_keeps_speech() -> None:
    sr = 32000
    silence = np.zeros(sr // 2, dtype=np.float32)
    speech = np.ones(sr, dtype=np.float32) * 0.2
    audio = np.concatenate([silence, speech, silence])
    trimmed = trim_silence_edges(audio, sr)
    assert trimmed.size < audio.size
    assert trimmed.size >= sr // 2


def test_preprocess_sample_audio_writes_cache(tmp_path) -> None:
    sample = tmp_path / "sample.wav"
    sr = 32000
    audio = np.ones(sr, dtype=np.float32) * 0.2
    import soundfile as sf

    sf.write(sample, audio, sr)
    cache_dir = tmp_path / "cache"
    out1 = preprocess_sample_audio(sample, cache_dir=cache_dir, denoise=True, trim_silence=False)
    out2 = preprocess_sample_audio(sample, cache_dir=cache_dir, denoise=True, trim_silence=False)
    assert out1 == out2
    assert out1.exists()
