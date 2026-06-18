from __future__ import annotations

import re
from dataclasses import dataclass

from sub_visual.config import FilterConfig

_URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)


@dataclass(frozen=True)
class FilterResult:
    accepted: bool
    reason: str | None = None


class SubtitleMessageFilter:
    def __init__(self, config: FilterConfig) -> None:
        self._config = config
        self._blocked = [kw.lower() for kw in config.blocked_keywords if kw]

    def evaluate(self, content: str) -> FilterResult:
        text = content.strip()
        if not text:
            return FilterResult(False, "empty")

        if self._config.block_commands and text.startswith("!"):
            return FilterResult(False, "command")

        if len(text) < self._config.min_length:
            return FilterResult(False, "too_short")

        if self._config.block_urls and _URL_PATTERN.search(text):
            return FilterResult(False, "url")

        lowered = text.lower()
        for keyword in self._blocked:
            if keyword in lowered:
                return FilterResult(False, f"blocked_keyword:{keyword}")

        return FilterResult(True)
