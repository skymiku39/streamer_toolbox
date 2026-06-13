from __future__ import annotations

from typing import Protocol


class SafetyFilter(Protocol):
    def filter_input(self, text: str) -> str | None:
        """過濾觀眾輸入；若應阻擋則回傳 None。"""

    def filter_output(self, text: str) -> str | None:
        """過濾角色輸出；若應阻擋則回傳 None。"""
