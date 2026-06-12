from __future__ import annotations


class TriggerMatcher:
    def __init__(self, prefixes: tuple[str, ...]) -> None:
        self._prefixes = tuple(prefix.strip() for prefix in prefixes if prefix.strip())

    def extract_question(self, content: str) -> str | None:
        text = content.strip()
        if not text:
            return None
        lowered = text.lower()
        for prefix in self._prefixes:
            if lowered.startswith(prefix.lower()):
                question = text[len(prefix) :].strip()
                if question:
                    return question
        return None
