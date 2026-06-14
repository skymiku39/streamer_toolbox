"""YouTube 直播聊天室讀取器。

底層使用 [`pytchat`](https://github.com/taizan-hokuto/pytchat)，
它會自行生成 InnerTube continuation token，
不需要去抓 YouTube HTML 頁面，可避開 YouTube 改版造成的 ParsingError。
完全不消耗 YouTube Data API Quota，亦不需要 API Key。
"""

from __future__ import annotations

import contextlib
import logging
import re
import signal
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pytchat

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _suppress_signal_in_thread() -> Iterator[None]:
    """Pytchat 在 __init__ 內無條件呼叫 signal.signal(SIGINT, ...)，
    在非 main thread 會丟 ValueError。
    這個 context manager 暫時把 signal.signal 替成 no-op 來繞過。"""

    if threading.current_thread() is threading.main_thread():
        yield
        return

    original = signal.signal

    def _noop_signal(_sig: int, _handler: Any) -> Any:
        return None

    signal.signal = _noop_signal  # type: ignore[assignment]
    try:
        yield
    finally:
        signal.signal = original  # type: ignore[assignment]


_YT_URL_PATTERNS = (
    re.compile(r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|live/|embed/|shorts/))([\w\-]{11})"),
    re.compile(r"[?&]v=([\w\-]{11})"),
)


def normalize_video_id(video: str) -> str:
    """從輸入抽出 11 碼影片 ID。"""

    video = video.strip()
    if re.fullmatch(r"[\w\-]{11}", video):
        return video

    for pattern in _YT_URL_PATTERNS:
        match = pattern.search(video)
        if match:
            return match.group(1)
    raise ValueError(f"無法從輸入解析出 YouTube 影片 ID: {video!r}")


def normalize_video_url(video: str) -> str:
    """將使用者輸入轉換成 YouTube 觀看網址。"""
    return f"https://www.youtube.com/watch?v={normalize_video_id(video)}"


@dataclass(slots=True)
class ChatMessage:
    """精簡後的聊天室訊息物件。"""

    message_id: str
    author_name: str
    author_id: str
    message: str
    timestamp: datetime
    message_type: str
    is_member: bool = False
    is_moderator: bool = False
    is_owner: bool = False
    is_verified: bool = False
    amount: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """序列化成 JSON 友善的 dict（供 WebSocket / API 使用）。"""
        return {
            "message_id": self.message_id,
            "author_name": self.author_name,
            "author_id": self.author_id,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "message_type": self.message_type,
            "is_member": self.is_member,
            "is_moderator": self.is_moderator,
            "is_owner": self.is_owner,
            "is_verified": self.is_verified,
            "amount": self.amount,
        }

    @classmethod
    def from_pytchat(cls, chat_obj: Any) -> "ChatMessage":
        author = getattr(chat_obj, "author", None)
        raw_getter = getattr(chat_obj, "json", None)
        raw = raw_getter() if callable(raw_getter) else {}
        if not isinstance(raw, dict):
            raw = {}

        ts_ms = getattr(chat_obj, "timestamp", 0) or 0
        if ts_ms:
            try:
                timestamp = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                timestamp = datetime.now(tz=timezone.utc)
        else:
            timestamp = datetime.now(tz=timezone.utc)

        amount_string = getattr(chat_obj, "amountString", "") or ""
        currency = getattr(chat_obj, "currency", "") or ""
        amount: str | None = None
        if amount_string:
            amount = f"{currency} {amount_string}".strip() if currency else amount_string

        return cls(
            message_id=getattr(chat_obj, "id", "") or "",
            author_name=getattr(author, "name", "Unknown") if author else "Unknown",
            author_id=getattr(author, "channelId", "") if author else "",
            message=getattr(chat_obj, "message", "") or "",
            timestamp=timestamp,
            message_type=getattr(chat_obj, "type", "textMessage") or "textMessage",
            is_member=bool(getattr(author, "isChatSponsor", False)) if author else False,
            is_moderator=bool(getattr(author, "isChatModerator", False)) if author else False,
            is_owner=bool(getattr(author, "isChatOwner", False)) if author else False,
            is_verified=bool(getattr(author, "isVerified", False)) if author else False,
            amount=amount,
            raw=raw,
        )


ChatHandler = Callable[[ChatMessage], None]


class LiveChatReader:
    """YouTube 直播聊天室讀取器。

    使用範例：

    ```python
    reader = LiveChatReader("https://www.youtube.com/watch?v=xxxxxxxxxxx")
    reader.on_message(lambda msg: print(msg.author_name, msg.message))
    reader.start()
    ```
    """

    def __init__(
        self,
        video: str,
        *,
        poll_interval: float = 1.0,
    ) -> None:
        self.video_id = normalize_video_id(video)
        self.url = f"https://www.youtube.com/watch?v={self.video_id}"
        self.poll_interval = max(0.2, float(poll_interval))

        self._handlers: list[ChatHandler] = []
        self._chat: Any | None = None
        self._stopped = False

    def on_message(self, handler: ChatHandler) -> ChatHandler:
        """註冊一個訊息處理函式（可重複呼叫註冊多個）。"""
        self._handlers.append(handler)
        return handler

    def _dispatch(self, message: ChatMessage) -> None:
        for handler in self._handlers:
            try:
                handler(message)
            except Exception:
                logger.exception("Handler 處理訊息時發生例外")

    def iter_messages(self) -> Iterator[ChatMessage]:
        """以產生器形式逐則回傳訊息（不會自動呼叫已註冊的 handler）。"""

        self._stopped = False
        with _suppress_signal_in_thread():
            self._chat = pytchat.create(video_id=self.video_id)
        try:
            while self._chat.is_alive() and not self._stopped:
                items = list(self._chat.get().sync_items())
                if not items:
                    if self._stopped:
                        break
                    time.sleep(self.poll_interval)
                    continue
                for item in items:
                    if self._stopped:
                        break
                    yield ChatMessage.from_pytchat(item)
        finally:
            self.close()

    def start(self) -> None:
        """啟動阻塞式監聽迴圈，將訊息派發給所有 handler。"""

        try:
            for message in self.iter_messages():
                self._dispatch(message)
        except KeyboardInterrupt:
            logger.info("使用者中斷，停止讀取聊天室")
            self.stop()

    def stop(self) -> None:
        """請求停止監聽迴圈。"""
        self._stopped = True
        self.close()

    def close(self) -> None:
        chat = self._chat
        self._chat = None
        if chat is None:
            return
        try:
            chat.terminate()
        except Exception:
            logger.debug("關閉 pytchat 時發生非致命錯誤", exc_info=True)
