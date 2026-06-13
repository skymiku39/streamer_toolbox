"""本機麥克風 → 16 kHz mono PCM chunks。"""

from __future__ import annotations

import contextlib
import logging
import threading
from collections.abc import Callable, Iterator
from queue import Empty, Full, Queue
from typing import Any, Protocol

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2
READ_BLOCK_FRAMES = 1600  # 100 ms @ 16 kHz


class InputStream(Protocol):
    def read(self, frames: int) -> tuple[Any, bool]: ...

    def __enter__(self) -> InputStream: ...

    def __exit__(self, *args: object) -> None: ...


StreamOpener = Callable[..., InputStream]


class MicAudioCapture:
    """背景執行緒從本機麥克風擷取音訊並切成固定秒數 PCM chunk。"""

    def __init__(
        self,
        *,
        chunk_seconds: float,
        device: int | str | None = None,
        on_chunk: Callable[[bytes], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        queue_maxsize: int = 32,
        stream_opener: StreamOpener | None = None,
    ) -> None:
        self._chunk_seconds = chunk_seconds
        self._chunk_bytes = int(SAMPLE_RATE * BYTES_PER_SAMPLE * self._chunk_seconds)
        self._device = device
        self._on_chunk = on_chunk
        self._on_error = on_error
        self._queue: Queue[bytes | None] = Queue(maxsize=queue_maxsize)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._stream_opener = stream_opener or _default_stream_opener

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="mic-audio", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with contextlib.suppress(Exception):
            self._queue.put_nowait(None)
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=5.0)

    def iter_chunks(self, timeout: float = 1.0) -> Iterator[bytes]:
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=timeout)
            except Empty:
                continue
            if item is None:
                break
            yield item

    def _deliver_chunk(self, chunk: bytes) -> None:
        if self._on_chunk is not None:
            self._on_chunk(chunk)
            return
        try:
            self._queue.put_nowait(chunk)
        except Full:
            with contextlib.suppress(Empty):
                self._queue.get_nowait()
            with contextlib.suppress(Full):
                self._queue.put_nowait(chunk)

    def _run(self) -> None:
        buf = bytearray()
        try:
            with self._stream_opener(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
                device=self._device,
                blocksize=READ_BLOCK_FRAMES,
            ) as stream:
                while not self._stop.is_set():
                    data, overflowed = stream.read(READ_BLOCK_FRAMES)
                    if overflowed:
                        logger.warning("MicAudioCapture input overflow")
                    if data is None:
                        break
                    raw = bytes(data)
                    if not raw:
                        break
                    buf.extend(raw)
                    while len(buf) >= self._chunk_bytes:
                        chunk = bytes(buf[: self._chunk_bytes])
                        del buf[: self._chunk_bytes]
                        self._deliver_chunk(chunk)
        except Exception as exc:
            self._emit_error(f"麥克風擷取失敗: {exc}")
        finally:
            if self._on_chunk is None:
                with contextlib.suppress(Exception):
                    self._queue.put_nowait(None)
            logger.info("MicAudioCapture 已結束 device=%s", self._device)

    def _emit_error(self, msg: str) -> None:
        logger.error("%s", msg)
        if self._on_error:
            self._on_error(msg)


def _default_stream_opener(**kwargs: Any) -> InputStream:
    import sounddevice as sd

    return sd.RawInputStream(**kwargs)
