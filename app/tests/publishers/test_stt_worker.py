import struct
from types import SimpleNamespace

from ingress_twitch_audio.config import SttConfig
from ingress_twitch_audio.stt_worker import STTWorker
from pkg_safety import SttInputFilter


def _pcm_from_amplitude(amplitude: float, sample_count: int = 16000) -> bytes:
    value = int(amplitude * 32767)
    return struct.pack(f"<{sample_count}h", *([value] * sample_count))


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
        vad_filter=False,
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
    )
    worker = STTWorker(
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
        vad_filter=False,
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
    )
    segments: list[str] = []

    worker = STTWorker(
        config,
        model_loader=lambda: _mock_model("今天天氣真好"),
        on_segment=lambda seg: segments.append(seg.text),
    )
    pcm = _pcm_from_amplitude(0.3, sample_count=int(16000 * config.chunk_seconds))
    result = worker.transcribe_chunk(pcm)

    assert result is not None
    assert result.text == "今天天氣真好"
    assert result.start_sec == 0.0
    assert result.end_sec == 1.0
    assert segments == ["今天天氣真好"]


def test_transcribe_chunk_filters_hallucination() -> None:
    config = SttConfig(
        model_size="tiny",
        chunk_seconds=1.0,
        language="zh",
        device="cpu",
        compute_type="int8",
        cpu_threads=1,
        rms_gate=0.01,
        filter_hallucinations=True,
        vad_filter=False,
        condition_on_previous_text=False,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
    )
    worker = STTWorker(
        config,
        model_loader=lambda: _mock_model("thanks for watching"),
    )
    pcm = _pcm_from_amplitude(0.3, sample_count=int(16000 * config.chunk_seconds))
    assert worker.transcribe_chunk(pcm) is None
