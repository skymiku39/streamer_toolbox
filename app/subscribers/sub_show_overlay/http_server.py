from __future__ import annotations

import json
import mimetypes
import threading
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from typing import Callable

from sub_show_overlay.ipc import read_overlay_snapshot


class OverlayHttpServer:
    """Serve overlay HTML and JSON snapshot for OBS Browser Source."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        snapshot_provider: Callable[[], dict],
    ) -> None:
        self._host = host
        self._port = port
        self._snapshot_provider = snapshot_provider
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}/"

    def start(self) -> None:
        handler = partial(_OverlayRequestHandler, snapshot_provider=self._snapshot_provider)
        self._server = ThreadingHTTPServer((self._host, self._port), handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="overlay-http",
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


class _OverlayRequestHandler(BaseHTTPRequestHandler):
    snapshot_provider: Callable[[], dict]

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/index.html"}:
            self._serve_asset("overlay.html", "text/html; charset=utf-8")
            return
        if self.path == "/snapshot.json":
            payload = self.snapshot_provider()
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def _serve_asset(self, filename: str, content_type: str) -> None:
        try:
            body = _read_asset(filename)
        except (OSError, FileNotFoundError):
            self.send_error(404)
            return
        guessed = mimetypes.guess_type(filename)[0] or content_type
        self.send_response(200)
        self.send_header("Content-Type", guessed)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _read_asset(filename: str) -> bytes:
    asset = resources.files("sub_show_overlay") / "assets" / filename
    return asset.read_bytes()
