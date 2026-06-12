from __future__ import annotations

import sys
from dataclasses import dataclass

from pkg_events import ChatMessageEvent

from sub_visual.config import SubtitleConfig
from sub_visual.filter import MessageFilter
from sub_visual.sender import SubtitleSender, build_sender


@dataclass
class SubtitleUpdate:
    text: str
    backend: str
    message_id: str
    filtered: bool = False
    filter_reason: str | None = None


class SubtitleService:
    """將 chat.message 格式化並輸出為字幕。"""

    def __init__(self, config: SubtitleConfig) -> None:
        self.config = config
        self.last_line = ""
        self._filter = MessageFilter(config.filter)
        self._sender, fallback_reason = build_sender(
            backend=config.backend,
            sender_name=config.sender_name,
            output_file=config.output_file,
        )
        self._fallback_reason = fallback_reason
        if fallback_reason:
            self._log_fallback(fallback_reason)

    @property
    def sender(self) -> SubtitleSender:
        return self._sender

    @property
    def fallback_reason(self) -> str | None:
        return self._fallback_reason

    def reload_config(self, config: SubtitleConfig) -> None:
        self._sender.close()
        self.config = config
        self._filter = MessageFilter(config.filter)
        self._sender, fallback_reason = build_sender(
            backend=config.backend,
            sender_name=config.sender_name,
            output_file=config.output_file,
        )
        self._fallback_reason = fallback_reason
        if fallback_reason:
            self._log_fallback(fallback_reason)

    def handle_chat_message(self, event: ChatMessageEvent) -> SubtitleUpdate | None:
        filter_result = self._filter.evaluate(event.content)
        if not filter_result.accepted:
            return SubtitleUpdate(
                text="",
                backend=self._sender.backend_name,
                message_id=event.message_id,
                filtered=True,
                filter_reason=filter_result.reason,
            )

        username = event.author_name
        message = event.content.strip()
        text = self.config.format_template.format(username=username, message=message)
        if len(text) > self.config.max_chars:
            text = text[: self.config.max_chars] + "..."

        self._sender.send_text(text)
        self.last_line = text
        return SubtitleUpdate(
            text=text,
            backend=self._sender.backend_name,
            message_id=event.message_id,
        )

    def close(self) -> None:
        self._sender.close()

    def _log_fallback(self, reason: str) -> None:
        print(
            f"[sub-visual] Spout2 不可用，已降級為文字檔輸出: {reason}",
            file=sys.stderr,
            flush=True,
        )
