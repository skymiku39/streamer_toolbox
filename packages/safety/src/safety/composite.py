from __future__ import annotations

from collections.abc import Iterable

from safety.protocol import SafetyFilter


class CompositeSafetyFilter:
    """依序套用多個 SafetyFilter；任一層回傳 None 即視為阻擋。

    各層皆遵循同一 SafetyFilter 介面（Open/Closed）：新增防護只需加入 filter，
    不必修改既有實作。前一層的輸出會作為下一層的輸入，允許逐層淨化。
    """

    def __init__(self, filters: Iterable[SafetyFilter]) -> None:
        self._filters = tuple(filters)

    def filter_input(self, text: str) -> str | None:
        return self._apply(text, output=False)

    def filter_output(self, text: str) -> str | None:
        return self._apply(text, output=True)

    def _apply(self, text: str, *, output: bool) -> str | None:
        current = text.strip()
        if not current:
            return None
        for safety_filter in self._filters:
            result = (
                safety_filter.filter_output(current)
                if output
                else safety_filter.filter_input(current)
            )
            if result is None:
                return None
            current = result
        return current or None
