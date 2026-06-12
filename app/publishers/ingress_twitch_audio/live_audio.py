"""streamlink → ffmpeg：16 kHz mono PCM chunks。"""

from __future__ import annotations

import contextlib
import logging
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from queue import Empty, Full, Queue

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2


def _resolve_streamlink() -> str:
    exe = shutil.which("streamlink")
    if exe:
        return exe
    candidate = Path(sys.executable).parent / (
        "streamlink.exe" if sys.platform == "win32" else "streamlink"
    )
    if candidate.is_file():
        return str(candidate)
    raise FileNotFoundError("找不到 streamlink，請執行 uv sync")


class LiveAudioCapture:
    """背景執行緒從 Twitch 直播拉音訊並切成固定秒數 PCM chunk。"""

    def __init__(
        self,
        channel: str,
        *,
        chunk_seconds: float,
        on_chunk: Callable[[bytes], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        queue_maxsize: int = 32,
    ) -> None:
        self._channel = channel.strip().lower().lstrip("#")
        self._chunk_seconds = chunk_seconds
        self._chunk_bytes = int(SAMPLE_RATE * BYTES_PER_SAMPLE * self._chunk_seconds)
        self._on_chunk = on_chunk
        self._on_error = on_error
        self._queue: Queue[bytes | None] = Queue(maxsize=queue_maxsize)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._procs: list[subprocess.Popen[bytes]] = []

    @property
    def channel(self) -> str:
        return self._channel

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="live-audio", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        for proc in self._procs:
            with contextlib.suppress(Exception):
                proc.terminate()
        self._procs.clear()
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
        url = f"https://www.twitch.tv/{self._channel}"
        streamlink = _resolve_streamlink()
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            self._emit_error("找不到 ffmpeg")
            return

        try:
            sl = subprocess.Popen(
                [streamlink, url, "audio_only", "-O"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            ff = subprocess.Popen(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    "pipe:0",
                    "-f",
                    "s16le",
                    "-acodec",
                    "pcm_s16le",
                    "-ar",
                    str(SAMPLE_RATE),
                    "-ac",
                    "1",
                    "pipe:1",
                ],
                stdin=sl.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            if sl.stdout:
                sl.stdout.close()
            self._procs = [sl, ff]
        except Exception as exc:
            self._emit_error(f"啟動音訊管線失敗: {exc}")
            if self._on_chunk is None:
                self._queue.put(None)
            return

        assert ff.stdout is not None
        buf = bytearray()
        try:
            while not self._stop.is_set():
                data = ff.stdout.read(self._chunk_bytes)
                if not data:
                    if sl.poll() is not None or ff.poll() is not None:
                        break
                    continue
                buf.extend(data)
                while len(buf) >= self._chunk_bytes:
                    chunk = bytes(buf[: self._chunk_bytes])
                    del buf[: self._chunk_bytes]
                    self._deliver_chunk(chunk)
        except Exception as exc:
            self._emit_error(f"讀取音訊失敗: {exc}")
        finally:
            for proc in self._procs:
                with contextlib.suppress(Exception):
                    proc.terminate()
            self._procs.clear()
            if self._on_chunk is None:
                self._queue.put(None)
            logger.info("LiveAudioCapture 已結束 channel=%s", self._channel)

    def _emit_error(self, msg: str) -> None:
        logger.error("%s", msg)
        if self._on_error:
            self._on_error(msg)
