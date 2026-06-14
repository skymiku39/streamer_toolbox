"""WebSocket 伺服器：將 LiveChatReader 串流推送給 Tauri 前端。"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import threading
from typing import Any

import websockets
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed
from websockets.server import WebSocketServerProtocol

from .reader import LiveChatReader

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class ChatSession:
    """單一 WebSocket 連線的聊天室讀取工作階段。"""

    def __init__(self, websocket: WebSocketServerProtocol) -> None:
        self.websocket = websocket
        self.reader: LiveChatReader | None = None
        self.thread: threading.Thread | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self._stop_event = threading.Event()

    async def send(self, payload: dict[str, Any]) -> None:
        await self.websocket.send(json.dumps(payload, ensure_ascii=False))

    async def handle_message(self, data: dict[str, Any]) -> None:
        action = data.get("action")
        if action == "start":
            video = str(data.get("video", "")).strip()
            if not video:
                await self.send(
                    {"type": "status", "status": "error", "message": "缺少 video 參數"}
                )
                return
            await self.start_reading(video)
        elif action == "stop":
            await self.stop_reading()
            await self.send({"type": "status", "status": "stopped", "message": "已停止監聽"})
        elif action == "ping":
            await self.send({"type": "pong"})
        else:
            await self.send(
                {
                    "type": "status",
                    "status": "error",
                    "message": f"未知 action: {action}",
                }
            )

    async def start_reading(self, video: str) -> None:
        await self.stop_reading()
        await self.send(
            {
                "type": "status",
                "status": "connecting",
                "message": f"正在連線 {video} ...",
            }
        )

        self.loop = asyncio.get_running_loop()
        self._stop_event.clear()
        self.reader = LiveChatReader(video)

        def _run_reader() -> None:
            assert self.loop is not None
            try:
                for message in self.reader.iter_messages():  # type: ignore[union-attr]
                    if self._stop_event.is_set():
                        break
                    payload = {"type": "chat", "payload": message.to_dict()}
                    asyncio.run_coroutine_threadsafe(self.send(payload), self.loop)
                if not self._stop_event.is_set():
                    asyncio.run_coroutine_threadsafe(
                        self.send(
                            {
                                "type": "status",
                                "status": "stopped",
                                "message": "聊天室串流結束",
                            }
                        ),
                        self.loop,
                    )
            except Exception as exc:
                logger.exception("讀取聊天室時發生錯誤")
                asyncio.run_coroutine_threadsafe(
                    self.send(
                        {
                            "type": "status",
                            "status": "error",
                            "message": f"{type(exc).__name__}: {exc}",
                        }
                    ),
                    self.loop,
                )

        self.thread = threading.Thread(target=_run_reader, daemon=True, name="chat-reader")
        self.thread.start()
        await self.send(
            {
                "type": "status",
                "status": "connected",
                "message": "已連線，開始接收訊息",
            }
        )

    async def stop_reading(self) -> None:
        self._stop_event.set()
        if self.reader is not None:
            self.reader.stop()
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=5)
        self.thread = None
        self.reader = None


async def _connection_handler(websocket: WebSocketServerProtocol) -> None:
    session = ChatSession(websocket)
    try:
        async for raw in websocket:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await session.send(
                    {"type": "status", "status": "error", "message": "無效的 JSON 格式"}
                )
                continue
            if not isinstance(data, dict):
                await session.send(
                    {"type": "status", "status": "error", "message": "訊息必須是 JSON 物件"}
                )
                continue
            await session.handle_message(data)
    except ConnectionClosed:
        logger.debug("WebSocket 連線已關閉")
    finally:
        await session.stop_reading()


async def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    async with serve(_connection_handler, host, port):
        logger.info("WebSocket server listening on ws://%s:%s", host, port)
        await asyncio.Future()


def _ensure_utf8_stdout() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    _ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description="TubeChat Lens WebSocket 伺服器")
    parser.add_argument("--host", default=DEFAULT_HOST, help="綁定 host (預設 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="綁定 port (預設 8765)")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("websockets.server").setLevel(logging.WARNING)

    try:
        asyncio.run(run_server(args.host, args.port))
    except KeyboardInterrupt:
        logger.info("伺服器已停止")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
