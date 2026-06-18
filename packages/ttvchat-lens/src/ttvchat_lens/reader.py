"""Twitch 直播聊天室讀取器。

直接連線 Twitch 官方 IRC over WebSocket
(`wss://irc-ws.chat.twitch.tv:443`)，以匿名 `justinfan{random}` 帳號
唯讀加入聊天室。**完全不需要 OAuth、API Key、Client ID**。

IRC v3 tags / commands / membership capability 都會啟用，
可以拿到 emote、color、badges、bits、subscriber 等 metadata。
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from queue import Empty, Queue
from typing import Any

from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)

TWITCH_IRC_URL = "wss://irc-ws.chat.twitch.tv:443"

_CHANNEL_PATTERNS = (
    re.compile(r"twitch\.tv/(?:popout/)?([A-Za-z0-9_]{2,32})", re.IGNORECASE),
    re.compile(r"^#?([A-Za-z0-9_]{2,32})$"),
)


def parse_twitch_channel(channel: str) -> str:
    """從輸入抽出 Twitch 頻道名（小寫，不含 # 前綴）。"""

    channel = channel.strip()
    for pattern in _CHANNEL_PATTERNS:
        match = pattern.search(channel)
        if match:
            return match.group(1).lower()
    raise ValueError(f"無法從輸入解析出 Twitch 頻道名: {channel!r}")


def channel_url(channel: str) -> str:
    """以正規化後的頻道名組出 Twitch 觀看網址。"""
    return f"https://www.twitch.tv/{parse_twitch_channel(channel)}"


# ---------------------------------------------------------------------------
# IRC line parser
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class IRCLine:
    """已剖析的 IRC 一行訊息。"""

    tags: dict[str, str]
    prefix: str
    command: str
    params: list[str]
    trailing: str

    @property
    def nick(self) -> str:
        if "!" in self.prefix:
            return self.prefix.split("!", 1)[0]
        return self.prefix


_TAG_UNESCAPE = {
    r"\:": ";",
    r"\s": " ",
    r"\\": "\\",
    r"\r": "\r",
    r"\n": "\n",
}


def _unescape_tag(value: str) -> str:
    out = []
    i = 0
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value):
            esc = value[i : i + 2]
            out.append(_TAG_UNESCAPE.get(esc, value[i + 1]))
            i += 2
        else:
            out.append(value[i])
            i += 1
    return "".join(out)


def parse_irc_line(line: str) -> IRCLine | None:
    """解析單行 IRC 訊息。回傳 None 代表空白行。"""

    line = line.rstrip("\r\n")
    if not line:
        return None

    tags: dict[str, str] = {}
    if line.startswith("@"):
        tag_section, _, line = line.partition(" ")
        for kv in tag_section[1:].split(";"):
            if "=" in kv:
                k, v = kv.split("=", 1)
                tags[k] = _unescape_tag(v)
            else:
                tags[kv] = ""

    prefix = ""
    if line.startswith(":"):
        prefix, _, line = line[1:].partition(" ")

    trailing = ""
    if " :" in line:
        line, _, trailing = line.partition(" :")
    params = line.split(" ") if line else []
    command = params.pop(0) if params else ""

    return IRCLine(
        tags=tags,
        prefix=prefix,
        command=command,
        params=params,
        trailing=trailing,
    )


# ---------------------------------------------------------------------------
# Chat message dataclass
# ---------------------------------------------------------------------------


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
    color: str | None = None
    amount: str | None = None
    bits: int = 0
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
            "color": self.color,
            "amount": self.amount,
            "bits": self.bits,
        }

    @classmethod
    def from_irc(cls, channel: str, irc: IRCLine) -> ChatMessage:
        tags = irc.tags
        nick = irc.nick
        display_name = tags.get("display-name") or nick or "anonymous"

        ts_ms_str = tags.get("tmi-sent-ts")
        if ts_ms_str and ts_ms_str.isdigit():
            try:
                timestamp = datetime.fromtimestamp(int(ts_ms_str) / 1000, tz=UTC)
            except (OverflowError, OSError, ValueError):
                timestamp = datetime.now(tz=UTC)
        else:
            timestamp = datetime.now(tz=UTC)

        badges_raw = tags.get("badges", "") or ""
        badges = {b.split("/", 1)[0] for b in badges_raw.split(",") if b}

        is_owner = "broadcaster" in badges or nick.lower() == channel.lower()
        is_moderator = tags.get("mod") == "1" or "moderator" in badges or "vip" in badges
        is_member = tags.get("subscriber") == "1" or "subscriber" in badges or "founder" in badges
        is_verified = "partner" in badges or "verified" in badges

        bits_str = tags.get("bits", "")
        bits = int(bits_str) if bits_str.isdigit() else 0
        amount: str | None = None
        if bits > 0:
            amount = f"{bits} bits"

        return cls(
            message_id=tags.get("id", "") or "",
            author_name=display_name,
            author_id=tags.get("user-id", "") or "",
            message=irc.trailing,
            timestamp=timestamp,
            message_type="textMessage",
            is_member=is_member,
            is_moderator=is_moderator,
            is_owner=is_owner,
            is_verified=is_verified,
            color=tags.get("color") or None,
            amount=amount,
            bits=bits,
            raw=dict(tags),
        )

    @classmethod
    def system(
        cls,
        message: str,
        message_type: str = "system",
        channel: str = "",
    ) -> ChatMessage:
        return cls(
            message_id="",
            author_name="*",
            author_id="",
            message=message,
            timestamp=datetime.now(tz=UTC),
            message_type=message_type,
        )


ChatHandler = Callable[[ChatMessage], None]


# ---------------------------------------------------------------------------
# LiveChatReader
# ---------------------------------------------------------------------------


class LiveChatReader:
    """Twitch 直播聊天室讀取器（同步介面）。

    使用範例：

    ```python
    reader = LiveChatReader("https://www.twitch.tv/forsen")
    reader.on_message(lambda msg: print(msg.author_name, msg.message))
    reader.start()
    ```

    底層用 asyncio + websockets 跑 IRC，但對使用者暴露的是同步 generator
    `iter_messages()` 與阻塞式 `start()`。
    """

    def __init__(
        self,
        channel: str,
        *,
        nick: str | None = None,
        token: str = "SCHMOOPIIE",
        queue_size: int = 1024,
    ) -> None:
        self.channel = parse_twitch_channel(channel)
        self.url = channel_url(self.channel)
        self.nick = nick or f"justinfan{random.randint(10000, 99999)}"
        self.token = token

        self._handlers: list[ChatHandler] = []
        self._queue: Queue[ChatMessage | object] = Queue(maxsize=queue_size)
        self._sentinel = object()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._stop_event: asyncio.Event | None = None
        self._task: asyncio.Task[None] | None = None
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

    # ------------------------------------------------------------------
    # Async IRC core
    # ------------------------------------------------------------------

    async def _run_async(self) -> None:
        assert self._stop_event is not None
        try:
            async with ws_connect(
                TWITCH_IRC_URL,
                max_size=2**20,
                ping_interval=None,
            ) as ws:
                logger.debug("已連線 Twitch IRC: %s (nick=%s)", TWITCH_IRC_URL, self.nick)
                await ws.send(
                    "CAP REQ :twitch.tv/tags twitch.tv/commands twitch.tv/membership"
                )
                await ws.send(f"PASS {self.token}")
                await ws.send(f"NICK {self.nick}")
                await ws.send(f"JOIN #{self.channel}")

                recv_task = asyncio.create_task(self._recv_loop(ws))
                stop_task = asyncio.create_task(self._stop_event.wait())
                done, pending = await asyncio.wait(
                    {recv_task, stop_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()
                for t in done:
                    if t is recv_task and t.exception():
                        raise t.exception()  # type: ignore[misc]
        except ConnectionClosed as exc:
            self._enqueue(
                ChatMessage.system(
                    f"Twitch IRC 連線關閉: {exc.code} {exc.reason}", "disconnected"
                )
            )
        except Exception as exc:
            logger.exception("Twitch IRC 連線時發生錯誤")
            self._enqueue(
                ChatMessage.system(f"{type(exc).__name__}: {exc}", "error")
            )
        finally:
            self._queue.put(self._sentinel)

    async def _recv_loop(self, ws: Any) -> None:
        joined = False
        async for raw in ws:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            for line in raw.split("\r\n"):
                irc = parse_irc_line(line)
                if irc is None:
                    continue
                await self._handle_irc(ws, irc)
                if not joined and irc.command == "JOIN":
                    joined = True
                    self._enqueue(
                        ChatMessage.system(
                            f"已加入頻道 #{self.channel}", "joined", self.channel
                        )
                    )

    async def _handle_irc(self, ws: Any, irc: IRCLine) -> None:
        cmd = irc.command.upper()
        if cmd == "PING":
            # Twitch IRC keep-alive
            await ws.send(f"PONG :{irc.trailing or 'tmi.twitch.tv'}")
            return
        if cmd == "PRIVMSG":
            msg = ChatMessage.from_irc(self.channel, irc)
            self._enqueue(msg)
            return
        if cmd == "USERNOTICE":
            # Subscriptions / raids / gifts. Tag system-msg 為標準描述
            sys_msg = irc.tags.get("system-msg", "") or "USERNOTICE"
            sub_text = irc.trailing or sys_msg
            msg = ChatMessage.from_irc(self.channel, irc)
            msg.message_type = irc.tags.get("msg-id", "usernotice")
            msg.message = sys_msg + (f"｜{sub_text}" if sub_text and sub_text != sys_msg else "")
            self._enqueue(msg)
            return
        if cmd == "NOTICE":
            self._enqueue(
                ChatMessage.system(irc.trailing or "(Twitch NOTICE)", "notice", self.channel)
            )
            return
        if cmd == "RECONNECT":
            self._enqueue(
                ChatMessage.system("Twitch 要求重新連線", "reconnect", self.channel)
            )
        # 其他 IRC 控制訊息（001 ~ 376, ROOMSTATE, USERSTATE, GLOBALUSERSTATE）忽略

    def _enqueue(self, message: ChatMessage) -> None:
        if self._stopped:
            return
        try:
            self._queue.put_nowait(message)
        except Exception:
            # 滿了就丟掉最舊一筆
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(message)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Thread / lifecycle plumbing
    # ------------------------------------------------------------------

    def _start_loop(self) -> None:
        self._stopped = False
        self._loop = asyncio.new_event_loop()

        def _runner() -> None:
            assert self._loop is not None
            asyncio.set_event_loop(self._loop)
            self._stop_event = asyncio.Event()
            self._task = self._loop.create_task(self._run_async())
            try:
                self._loop.run_until_complete(self._task)
            except Exception:
                logger.exception("Reader loop 異常結束")
            finally:
                pending = asyncio.all_tasks(self._loop)
                for t in pending:
                    t.cancel()
                self._loop.run_until_complete(asyncio.sleep(0))
                self._loop.close()

        self._loop_thread = threading.Thread(target=_runner, daemon=True, name="ttvchat-irc")
        self._loop_thread.start()

    def iter_messages(self) -> Iterator[ChatMessage]:
        """以產生器形式逐則回傳訊息（不會自動呼叫已註冊的 handler）。"""

        self._start_loop()
        try:
            while True:
                try:
                    item = self._queue.get(timeout=0.5)
                except Empty:
                    if self._stopped:
                        break
                    continue
                if item is self._sentinel:
                    break
                assert isinstance(item, ChatMessage)
                yield item
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
        loop = self._loop
        stop_event = self._stop_event
        if loop is not None and stop_event is not None and not loop.is_closed():
            loop.call_soon_threadsafe(stop_event.set)
        self.close()

    def close(self) -> None:
        self._stopped = True
        thread = self._loop_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=5)
        self._loop = None
        self._loop_thread = None
        self._stop_event = None
        self._task = None
