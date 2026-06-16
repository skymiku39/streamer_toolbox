from __future__ import annotations

import struct
import time

from ingress_local_audio.config import LocalAudioConfig
from ingress_local_audio.local_audio import SAMPLE_RATE, MicAudioCapture


def _pcm_chunk(seconds: float, amplitude: float = 0.2) -> bytes:
    sample_count = int(SAMPLE_RATE * seconds)
    value = int(amplitude * 32767)
    return struct.pack(f"<{sample_count}h", *([value] * sample_count))


class _FakeStream:
    def __init__(self, frames: list[bytes]) -> None:
        self._frames = list(frames)
        self._index = 0

    def read(self, frames: int) -> tuple[memoryview, bool]:
        if self._index >= len(self._frames):
            return memoryview(b""), False
        data = self._frames[self._index]
        self._index += 1
        return memoryview(data), False

    def __enter__(self) -> _FakeStream:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_local_audio_config_parses_device_index(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_AUDIO_DEVICE", "3")
    config = LocalAudioConfig.from_env()
    assert config.device == 3


def test_mic_audio_capture_delivers_fixed_chunks() -> None:
    chunk_seconds = 0.2
    chunk_bytes = int(SAMPLE_RATE * 2 * chunk_seconds)
    block = _pcm_chunk(0.1)
    delivered: list[bytes] = []

    def opener(**kwargs: object) -> _FakeStream:
        # 0.1s blocks × 4 = 0.4s → 2 full chunks @ 0.2s
        return _FakeStream([block, block, block, block])

    capture = MicAudioCapture(
        chunk_seconds=chunk_seconds,
        on_chunk=delivered.append,
        stream_opener=opener,
    )
    capture.start()
    deadline = time.time() + 2.0
    while time.time() < deadline and len(delivered) < 2:
        time.sleep(0.05)
    capture.stop()

    assert len(delivered) >= 2
    assert len(delivered[0]) == chunk_bytes


def test_mic_audio_capture_iter_chunks() -> None:
    block = _pcm_chunk(0.1)
    capture = MicAudioCapture(
        chunk_seconds=0.1,
        stream_opener=lambda **kwargs: _FakeStream([block]),
    )
    capture.start()
    chunks = list(capture.iter_chunks(timeout=0.5))
    capture.stop()
    assert len(chunks) == 1
    assert len(chunks[0]) == int(SAMPLE_RATE * 2 * 0.1)
