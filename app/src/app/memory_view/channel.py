from __future__ import annotations

import os

from stream_store import StreamTextStore, resolve_session_for_channel

from app.memory_view.service import MemoryViewService


def default_channel() -> str | None:
    return (
        os.environ.get("MEMORY_BOARD_CHANNEL")
        or os.environ.get("TWITCH_CHANNEL")
        or ""
    ).strip() or None
