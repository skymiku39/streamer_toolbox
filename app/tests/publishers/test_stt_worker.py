import struct
from types import SimpleNamespace

import numpy as np

from ingress_twitch_audio.stt_worker import StreamingSTTWorker
from safety import SttInputFilter
from stt_core import SttConfig


def _pcm_from_amplitude(amplitude: float, sample_count: int = 16000) -> bytes:
    value = int(amplitude * 32767)
    return struct.pack(f"<{sample_count}h", *([value] * sample_count))


def _pcm_from_sine(amplitude: float, sample_count: int = 16000, freq_hz: float = 440.0) -> bytes:
    t = np.arange(sample_count, dtype=np.float64) / 16000.0
    wave = (amplitude * np.sin(2.0 * np.pi * freq_hz * t)).astype(np.float32)
    samples = np.clip(wave * 32767.0, -32768, 32767).astype(np.int16)
    return struct.pack(f"<{sample_count}h", *samples.tolist())


def _mock_model(text: str):
    def transcribe(audio, **kwargs):
        del audio, kwargs

        def segments():
            yield SimpleNamespace(
                text=text,
                no_speech_prob=0.1,
                avg_logprob=-0.2,
            )

        return segments(), SimpleNamespace()

    return SimpleNamespace(transcribe=transcribe)


def test_transcribe_chunk_skips_silent_audio() -> None:
    config = SttConfig.from_env()
    config = SttConfig(
        model_size=config.model_size,
        chunk_seconds=1.0,
        language="zh",
        device="cpu",
        compute_type="int8",
        cpu_threads=1,
        rms_gate=0.05,
        filter_hallucinations=True,
        hallucination_rms_gate=0.02,
        hallucination_speech_band_min=0.25,
        hallucination_spectral_flatness_max=0.35,
        vad_filter=False,
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
    )
    worker = StreamingSTTWorker(
        config,
        input_filter=SttInputFilter(rms_gate=0.05),
        model_loader=lambda: _mock_model("不該出現"),
    )
    result = worker.transcribe_chunk(_pcm_from_amplitude(0.001))
    assert result is None


def test_transcribe_chunk_publishes_segment() -> None:
    config = SttConfig(
        model_size="tiny",
        chunk_seconds=1.0,
        language="zh",
        device="cpu",
        compute_type="int8",
        cpu_threads=1,
        rms_gate=0.01,
        filter_hallucinations=True,
        hallucination_rms_gate=0.02,
        hallucination_speech_band_min=0.25,
        hallucination_spectral_flatness_max=0.35,
        vad_filter=False,
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
    )
    segments: list[str] = []

    worker = StreamingSTTWorker(
        config,
        model_loader=lambda: _mock_model("今天天氣真好"),
        on_segment=lambda seg: segments.append(seg.text),
    )
    pcm = _pcm_from_sine(0.3, sample_count=int(16000 * config.chunk_seconds))
    result = worker.transcribe_chunk(pcm)

    assert result is not None
    assert result.text == "今天天氣真好"
    assert result.start_sec == 0.0
    assert result.end_sec == 1.0
    assert result.confidence > 0.8
    assert segments == ["今天天氣真好"]


def test_transcribe_chunk_filters_hallucination_on_quiet_audio() -> None:
    config = SttConfig(
        model_size="tiny",
        chunk_seconds=1.0,
        language="zh",
        device="cpu",
        compute_type="int8",
        cpu_threads=1,
        rms_gate=0.001,
        filter_hallucinations=True,
        hallucination_rms_gate=0.02,
        hallucination_speech_band_min=0.25,
        hallucination_spectral_flatness_max=0.35,
        vad_filter=False,
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
    )
    worker = StreamingSTTWorker(
        config,
        model_loader=lambda: _mock_model("thanks for watching"),
    )
    pcm = _pcm_from_amplitude(0.008, sample_count=int(16000 * config.chunk_seconds))
    assert worker.transcribe_chunk(pcm) is None


def test_transcribe_chunk_keeps_speech_on_loud_audio_without_hallucination_filter() -> None:
    config = SttConfig(
        model_size="tiny",
        chunk_seconds=1.0,
        language="zh",
        device="cpu",
        compute_type="int8",
        cpu_threads=1,
        rms_gate=0.01,
        filter_hallucinations=True,
        hallucination_rms_gate=0.02,
        hallucination_speech_band_min=0.25,
        hallucination_spectral_flatness_max=0.35,
        vad_filter=False,
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
    )
    worker = StreamingSTTWorker(
        config,
        model_loader=lambda: _mock_model("thanks for watching"),
    )
    pcm = _pcm_from_sine(0.3, sample_count=int(16000 * config.chunk_seconds))
    result = worker.transcribe_chunk(pcm)
    assert result is not None
    assert result.text == "thanks for watching"
