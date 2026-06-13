# -*- coding: utf-8 -*-
"""Legacy entry point — 請改用 `uv run python -m app.memory_view` 或 scripts/show_summaries.py。"""
from __future__ import annotations

import sys

from app.memory_view.__main__ import main


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.extend(["--list-sessions"])
    raise SystemExit(main())
