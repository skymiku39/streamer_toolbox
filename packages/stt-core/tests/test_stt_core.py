from __future__ import annotations

from stt_core import BaseSTTWorker, SttConfig, TranscriptSegment, pcm_to_float32


def _base_kwargs() -> dict:
    return {
        "model_size": "medium",
        "chunk_seconds": 4.0,
        "language": "zh",
        "device": "cpu",
        "compute_type": "int8",
        "cpu_threads": 4,
        "rms_gate": 0.004,
        "filter_hallucinations": True,
        "hallucination_rms_gate": 0.02,
        "hallucination_speech_band_min": 0.25,
        "hallucination_spectral_flatness_max": 0.35,
        "vad_filter": False,
        "condition_on_previous_text": True,
        "no_speech_threshold": 0.85,
        "log_prob_threshold": -1.0,
        "compression_ratio_threshold": 2.4,
    }


def test_denoise_fields_default_when_omitted() -> None:
    config = SttConfig(**_base_kwargs())
    assert config.denoise_enabled is True
    assert config.denoise_hp_cutoff_hz == 80.0
    assert config.denoise_gate_ratio == 0.08


def test_from_env_reads_denoise(monkeypatch) -> None:
    monkeypatch.setenv("STT_DENOISE", "0")
    monkeypatch.setenv("STT_DENOISE_HP_HZ", "120")
    config = SttConfig.from_env()
    assert config.denoise_enabled is False
    assert config.denoise_hp_cutoff_hz == 120.0


def test_pcm_to_float32_scales_int16() -> None:
    pcm = (32767).to_bytes(2, "little", signed=True)
    audio = pcm_to_float32(pcm)
    assert audio.shape == (1,)
    assert abs(audio[0] - (32767 / 32768.0)) < 1e-6


def test_base_worker_builds_default_filter() -> None:
    worker = BaseSTTWorker(SttConfig(**_base_kwargs()))
    assert worker._input_filter.rms_gate == 0.004  # noqa: SLF001
    assert worker.wait_until_ready(timeout=0.0) is False


def test_transcript_segment_defaults() -> None:
    seg = TranscriptSegment(text="hi", start_sec=0.0, end_sec=1.0)
    assert seg.confidence == 0.0
