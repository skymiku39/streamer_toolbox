from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from app.memory_view.service import MemoryViewService

_BOARD_HTML = (Path(__file__).resolve().parent / "assets" / "board.html").read_text(
    encoding="utf-8"
)


@dataclass
class MemoryBoardState:
    _revision: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def bump(self) -> None:
        with self._lock:
            self._revision += 1

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision


class MemoryBoardHttpServer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        service: MemoryViewService,
        state: MemoryBoardState,
    ) -> None:
        self._host = host
        self._port = port
        self._service = service
        self._state = state
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}/"

    def start(self) -> None:
        service = self._service
        state = self._state

        class Handler(_BoardRequestHandler):
            pass

        Handler.service = service
        Handler.state = state
        self._server = ThreadingHTTPServer((self._host, self._port), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="memory-board-http",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None


class _BoardRequestHandler(BaseHTTPRequestHandler):
    service: MemoryViewService
    state: MemoryBoardState

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/index.html"}:
            self._send_text(200, _BOARD_HTML, "text/html; charset=utf-8")
            return
        if self.path == "/api/meta":
            self._send_json({"revision": self.state.revision})
            return
        if self.path == "/api/sessions":
            self._send_json(self.service.sessions_payload(revision=self.state.revision))
            return
        prefix = "/api/sessions/"
        if self.path.startswith(prefix) and self.path.endswith("/summaries"):
            session_part = self.path[len(prefix) : -len("/summaries")]
            session_id = unquote(session_part)
            self._send_json(
                self.service.summaries_payload(session_id, revision=self.state.revision)
            )
            return
        self.send_error(404)

    def _send_json(self, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, status: int, text: str, content_type: str) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
