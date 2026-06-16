from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class LayoutMode(StrEnum):
    CHAT = "chat"
    FREE = "free"
    BOTH = "both"


DEFAULT_OVERLAY_STYLE: dict[str, Any] = {
    "background_color": "rgba(0, 0, 0, 0.74)",
    "font_color": "#ffffff",
    "link_color": "#8fd3ff",
    "font_size": 28,
    "line_height": 1.45,
    "padding_x": 14,
    "padding_y": 10,
    "background_image": "",
}

DEFAULT_CHAT_IPC_PATH = Path("runtime/chat_overlay_state.json")
DEFAULT_FREE_IPC_PATH = Path("runtime/free_chat_overlay_state.json")
DEFAULT_HTTP_PORT = 8765
DEFAULT_MAX_LINES = 200
DEFAULT_QUEUE_SIZE = 500


@dataclass(frozen=True)
class OverlaySettings:
    layout: LayoutMode
    chat_ipc_path: Path
    free_ipc_path: Path
    http_port: int
    http_host: str
    max_lines: int
    queue_size: int
    style: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_OVERLAY_STYLE))
    chat_width: int = 1920
    chat_height: int = 462
    free_width: int = 1920
    free_height: int = 462

    @property
    def ipc_paths(self) -> list[Path]:
        if self.layout == LayoutMode.CHAT:
            return [self.chat_ipc_path]
        if self.layout == LayoutMode.FREE:
            return [self.free_ipc_path]
        return [self.chat_ipc_path, self.free_ipc_path]


def _parse_layout(raw: str) -> LayoutMode:
    value = raw.strip().lower()
    try:
        return LayoutMode(value)
    except ValueError as exc:
        raise ValueError(
            f"unsupported layout mode: {raw!r} (expected chat, free, or both)"
        ) from exc


def overlay_settings_from_env() -> OverlaySettings:
    return OverlaySettings(
        layout=_parse_layout(os.environ.get("OVERLAY_LAYOUT", "chat")),
        chat_ipc_path=Path(os.environ.get("OVERLAY_IPC_PATH", str(DEFAULT_CHAT_IPC_PATH))),
        free_ipc_path=Path(os.environ.get("OVERLAY_FREE_IPC_PATH", str(DEFAULT_FREE_IPC_PATH))),
        http_port=int(os.environ.get("OVERLAY_HTTP_PORT", str(DEFAULT_HTTP_PORT))),
        http_host=os.environ.get("OVERLAY_HTTP_HOST", "127.0.0.1"),
        max_lines=int(os.environ.get("OVERLAY_MAX_LINES", str(DEFAULT_MAX_LINES))),
        queue_size=int(os.environ.get("OVERLAY_QUEUE_SIZE", str(DEFAULT_QUEUE_SIZE))),
    )
