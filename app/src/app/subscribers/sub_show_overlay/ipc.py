from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from sub_show_overlay.settings import DEFAULT_OVERLAY_STYLE

_SNAPSHOT_REPLACE_RETRIES = 6
_SNAPSHOT_RETRY_DELAYS = (0.01, 0.02, 0.04, 0.08, 0.12, 0.16)


class OverlaySnapshotWriter:
    """Write overlay state snapshots for Browser Source polling or local window IPC."""

    def __init__(
        self,
        ipc_path: Path,
        *,
        max_lines: int = 200,
        width: int = 1920,
        height: int = 462,
        style: dict[str, Any] | None = None,
    ) -> None:
        self._ipc_path = Path(ipc_path)
        self._max_lines = max(20, int(max_lines))
        self._width = width
        self._height = height
        self._style = dict(DEFAULT_OVERLAY_STYLE)
        if style:
            self._style.update(style)
        self._lines: deque[dict[str, Any]] = deque(maxlen=self._max_lines)
        self._emote_assets: dict[str, str] = {}
        self._badge_sources: dict[str, str] = {}
        self._write_lock = threading.Lock()
        self._last_snapshot_state_json = ""
        self._content_revision = 0
        self._presentation_revision = 0
        self._template_revision = 0

    @property
    def ipc_path(self) -> Path:
        return self._ipc_path

    @property
    def content_revision(self) -> int:
        return self._content_revision

    def append_entry(self, entry: dict[str, Any]) -> None:
        plain_text = str(entry.get("plain_text", "")).rstrip()
        if not plain_text:
            return
        self._lines.append(dict(entry))
        self._content_revision += 1
        self.write_snapshot()

    def merge_emote_assets(self, assets: dict[str, str]) -> None:
        if not assets:
            return
        updated = dict(self._emote_assets)
        updated.update(assets)
        if updated != self._emote_assets:
            self._emote_assets = updated
            self._content_revision += 1

    def merge_badge_sources(self, badge_sources: dict[str, str]) -> None:
        if not badge_sources:
            return
        updated = dict(self._badge_sources)
        updated.update(badge_sources)
        if updated != self._badge_sources:
            self._badge_sources = updated
            self._presentation_revision += 1
            self.write_snapshot()

    def snapshot_dict(self) -> dict[str, Any]:
        return {
            "version": 3,
            "content_revision": self._content_revision,
            "presentation_revision": self._presentation_revision,
            "template_revision": self._template_revision,
            "layout": {"width": self._width, "height": self._height},
            "style": dict(self._style),
            "emote_assets": dict(self._emote_assets),
            "badge_sources": dict(self._badge_sources),
            "lines": [dict(entry) for entry in self._lines],
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

    def write_snapshot(self) -> None:
        payload = self.snapshot_dict()
        snapshot_state_json = json.dumps(
            {key: value for key, value in payload.items() if key != "updated_at"},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        with self._write_lock:
            if snapshot_state_json == self._last_snapshot_state_json:
                return
            snapshot_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            if self._write_snapshot_text(snapshot_json):
                self._last_snapshot_state_json = snapshot_state_json

    def _write_snapshot_text(self, snapshot_json: str) -> bool:
        self._ipc_path.parent.mkdir(parents=True, exist_ok=True)
        last_error: Exception | None = None
        for attempt in range(_SNAPSHOT_REPLACE_RETRIES):
            temp_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=self._ipc_path.parent,
                    prefix=f"{self._ipc_path.stem}.",
                    suffix=".tmp",
                    delete=False,
                ) as handle:
                    handle.write(snapshot_json)
                    temp_path = Path(handle.name)
                os.replace(temp_path, self._ipc_path)
                return True
            except (PermissionError, OSError) as exc:
                last_error = exc
            finally:
                if temp_path is not None and temp_path.exists():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass
            if attempt < len(_SNAPSHOT_RETRY_DELAYS):
                time.sleep(_SNAPSHOT_RETRY_DELAYS[attempt])

        if last_error is not None:
            raise OSError(f"failed to write overlay snapshot to {self._ipc_path}: {last_error}")
        return False


def read_overlay_snapshot(ipc_path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(Path(ipc_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}
