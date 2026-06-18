"""Deprecated re-export shim：請改用 `from stt_core import ...`。

`TranscriptSegment` 與 `build_stt_segment_event` 已集中於 `stt_core`，
此處僅為向後相容保留別名；新程式碼應直接依賴 `stt_core`。
"""

from __future__ import annotations

from stt_core import TranscriptSegment, build_stt_segment_event

__all__ = ["TranscriptSegment", "build_stt_segment_event"]
