from __future__ import annotations

import os


def default_channel() -> str | None:
    return (
        os.environ.get("MEMORY_BOARD_CHANNEL")
        or os.environ.get("TWITCH_CHANNEL")
        or ""
    ).strip() or None
