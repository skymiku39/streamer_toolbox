from __future__ import annotations

import re
from dataclasses import dataclass

from pkg_events import ChatMessageEvent

_URL_PATTERN = re.compile(r"(https?://|www\.)", re.IGNORECASE)


@dataclass(frozen=True)
class MessageFilterConfig:
    skip_commands: bool = True
    skip_urls: bool = True
    blacklist: frozenset[str] = frozenset()
    max_length: int | None = 300
    template: str = "{author_name} 說 {content}"


class MessageFilter:
    """決定哪些 chat.message 應朗讀，以及朗讀文字格式。"""

    def __init__(self, config: MessageFilterConfig) -> None:
        self._config = config

    @property
    def config(self) -> MessageFilterConfig:
        return self._config

    def should_speak(self, event: ChatMessageEvent) -> bool:
        content = event.content.strip()
        if not content:
            return False

        if self._config.skip_commands and content.startswith("!"):
            return False

        if self._config.skip_urls and _URL_PATTERN.search(content):
            return False

        lowered = content.lower()
        for term in self._config.blacklist:
            if term and term.lower() in lowered:
                return False

        if self._config.max_length is not None and len(content) > self._config.max_length:
            return False

        return True

    def format_text(self, event: ChatMessageEvent) -> str:
        return self._config.template.format(
            author_name=event.author_name,
            content=event.content.strip(),
            channel=event.channel or "",
            platform=event.platform,
        )
