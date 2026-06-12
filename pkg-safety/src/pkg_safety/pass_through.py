from __future__ import annotations


class PassThroughSafetyFilter:
    def filter_input(self, text: str) -> str | None:
        stripped = text.strip()
        return stripped if stripped else None

    def filter_output(self, text: str) -> str | None:
        stripped = text.strip()
        return stripped if stripped else None
