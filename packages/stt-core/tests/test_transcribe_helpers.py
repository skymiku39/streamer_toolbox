from __future__ import annotations

import math

import numpy as np

from stt_core.denoise import suppress_noise_for_stt
from stt_core.transcribe_helpers import logprob_to_confidence, resolve_initial_prompt
from stt_core.config import SttConfig


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


def test_from_env_reads_beam_and_prompt(monkeypatch) -> None:
    monkeypatch.setenv("STT_BEAM_SIZE", "3")
    monkeypatch.setenv("STT_INITIAL_PROMPT", "神人 理論派")
    monkeypatch.setenv("STT_CARRY_PROMPT", "0")
    config = SttConfig.from_env()
    assert config.beam_size == 3
    assert config.initial_prompt == "神人 理論派"
    assert config.carry_prompt is False


def test_logprob_to_confidence() -> None:
    assert logprob_to_confidence(-0.2) == math.exp(-0.2)
    assert logprob_to_confidence(None) == 0.0


def test_resolve_initial_prompt_combines_static_and_carry() -> None:
    config = SttConfig(
        **_base_kwargs(),
        initial_prompt="直播用語",
        carry_prompt=True,
    )
    prompt = resolve_initial_prompt(config, last_text="上一句台詞")
    assert prompt == "直播用語 上一句台詞"


def test_denoise_reduces_low_energy_frames() -> None:
    rng = np.random.default_rng(0)
    t = np.arange(16000, dtype=np.float32) / 16000.0
    speech = 0.3 * np.sin(2.0 * np.pi * 440.0 * t)
    tail = (rng.normal(0.0, 0.02, 8000)).astype(np.float32)
    audio = np.concatenate([speech, tail])
    out = suppress_noise_for_stt(audio, 16000, hp_cutoff_hz=80.0, gate_ratio=0.08)
    assert float(np.sqrt(np.mean(np.square(out[-8000:])))) < float(
        np.sqrt(np.mean(np.square(audio[-8000:]))),
    )
