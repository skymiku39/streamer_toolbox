from __future__ import annotations


class BlocklistSafetyFilter:
    def __init__(self, blocklist: frozenset[str] | None = None) -> None:
        self._blocklist = blocklist or frozenset()

    def filter_input(self, text: str) -> str | None:
        stripped = text.strip()
        if not stripped:
            return None
        lowered = stripped.lower()
        if any(word in lowered for word in self._blocklist):
            return None
        return stripped

    def filter_output(self, text: str) -> str | None:
        return self.filter_input(text)
