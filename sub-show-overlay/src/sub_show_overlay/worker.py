from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Any

from sub_show_overlay.ipc import OverlaySnapshotWriter
from sub_show_overlay.model import chat_payload_to_overlay_line, emote_assets_from_line
from sub_show_overlay.queue import OverlayMessageQueue
from sub_show_overlay.settings import LayoutMode, OverlaySettings


class OverlayRenderWorker:
    """Consume queued chat payloads and update overlay snapshot writers."""

    def __init__(
        self,
        settings: OverlaySettings,
        message_queue: OverlayMessageQueue,
    ) -> None:
        self._settings = settings
        self._message_queue = message_queue
        self._writers = self._build_writers(settings)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="overlay-render", daemon=True)
        self._processed = 0

    @property
    def writers(self) -> list[OverlaySnapshotWriter]:
        return list(self._writers)

    @property
    def primary_ipc_path(self) -> Path:
        return self._writers[0].ipc_path

    @property
    def processed_count(self) -> int:
        return self._processed

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def _build_writers(self, settings: OverlaySettings) -> list[OverlaySnapshotWriter]:
        writers: list[OverlaySnapshotWriter] = []
        if settings.layout in {LayoutMode.CHAT, LayoutMode.BOTH}:
            writers.append(
                OverlaySnapshotWriter(
                    settings.chat_ipc_path,
                    max_lines=settings.max_lines,
                    width=settings.chat_width,
                    height=settings.chat_height,
                    style=settings.style,
                )
            )
        if settings.layout in {LayoutMode.FREE, LayoutMode.BOTH}:
            writers.append(
                OverlaySnapshotWriter(
                    settings.free_ipc_path,
                    max_lines=settings.max_lines,
                    width=settings.free_width,
                    height=settings.free_height,
                    style=settings.style,
                )
            )
        if not writers:
            raise ValueError("at least one overlay writer is required")
        return writers

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                batch = self._message_queue.drain_batch(max_items=32)
            except queue.Empty:
                continue
            if not batch:
                continue
            self._apply_batch(batch)

    def _apply_batch(self, batch: list[dict[str, Any]]) -> None:
        lines = []
        emote_assets: dict[str, str] = {}
        for payload in batch:
            try:
                line = chat_payload_to_overlay_line(payload)
            except (KeyError, TypeError, ValueError):
                continue
            lines.append(line)
            emote_assets.update(emote_assets_from_line(line))

        if not lines:
            return

        for writer in self._writers:
            writer.merge_emote_assets(emote_assets)
            for line in lines:
                writer.append_entry(line.to_entry())
        self._processed += len(lines)
