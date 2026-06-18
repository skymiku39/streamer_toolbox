"""Deprecated re-export shim：請改用 `from stt_core import SttConfig`。

保留此別名僅為向後相容；新程式碼應直接依賴 `stt_core`。
"""

from __future__ import annotations

from stt_core import SttConfig

__all__ = ["SttConfig"]
