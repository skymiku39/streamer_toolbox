"""一鍵啟動桌面 App：自動管理 WebSocket 後端 + Tauri 視窗。"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def desktop_dir() -> Path:
    return project_root() / "desktop"


def is_port_open(host: str, port: int, timeout: float = 0.3) -> bool:
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


async def wait_for_server(host: str, port: int, timeout: float = 30.0) -> bool:
    import websockets

    deadline = time.monotonic() + timeout
    ws_url = f"ws://{host}:{port}"
    while time.monotonic() < deadline:
        if not is_port_open(host, port):
            await asyncio.sleep(0.2)
            continue
        try:
            async with websockets.connect(
                ws_url, open_timeout=1.0, ping_interval=None
            ) as ws:
                await ws.send(json.dumps({"action": "ping"}))
                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(raw)
                if data.get("type") == "pong":
                    return True
        except Exception:
            await asyncio.sleep(0.3)
    return False


def ensure_desktop_deps(desktop: Path) -> None:
    if (desktop / "node_modules").exists():
        return
    npm = shutil.which("npm")
    if npm is None:
        raise RuntimeError("找不到 npm，請先安裝 Node.js >= 18")
    logger.info("首次執行，正在安裝 desktop 前端相依套件 ...")
    subprocess.run([npm, "install"], cwd=desktop, check=True)


def start_server(root: Path, host: str, port: int) -> subprocess.Popen[bytes] | None:
    if is_port_open(host, port):
        logger.info("WebSocket 後端已在 ws://%s:%s 執行，略過啟動", host, port)
        return None

    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("找不到 uv，請先安裝 uv")

    logger.info("正在啟動 WebSocket 後端 ws://%s:%s ...", host, port)
    return subprocess.Popen(
        [uv, "run", "tubechat-lens-server", "--host", host, "--port", str(port)],
        cwd=root,
        env=os.environ.copy(),
    )


def stop_server(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    logger.info("正在關閉 WebSocket 後端 ...")
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def run_tauri(desktop: Path) -> int:
    npm = shutil.which("npm")
    if npm is None:
        raise RuntimeError("找不到 npm，請先安裝 Node.js >= 18")

    env = os.environ.copy()
    env["TUBECHAT_LENS_SERVER_MANAGED"] = "1"
    logger.info("正在啟動 Tauri 桌面視窗 ...")
    result = subprocess.run([npm, "run", "tauri", "dev"], cwd=desktop, env=env)
    return result.returncode


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="一鍵啟動 TubeChat Lens 桌面 App（WebSocket 後端 + Tauri 視窗）",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    root = project_root()
    desktop = desktop_dir()
    if not desktop.exists():
        logger.error("找不到 desktop 目錄: %s", desktop)
        return 1

    server_proc: subprocess.Popen[bytes] | None = None
    exit_code = 1

    def _cleanup(*_args: object) -> None:
        stop_server(server_proc)

    if hasattr(signal, "SIGINT"):
        signal.signal(signal.SIGINT, lambda *_: (_cleanup(), sys.exit(130)))
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, lambda *_: (_cleanup(), sys.exit(143)))

    try:
        ensure_desktop_deps(desktop)
        server_proc = start_server(root, args.host, args.port)

        if server_proc is not None:
            ready = asyncio.run(wait_for_server(args.host, args.port))
            if not ready:
                logger.error("WebSocket 後端啟動逾時 (ws://%s:%s)", args.host, args.port)
                return 1
            logger.info("WebSocket 後端就緒")
        elif not is_port_open(args.host, args.port):
            logger.error("無法連線到 WebSocket 後端 ws://%s:%s", args.host, args.port)
            return 1

        exit_code = run_tauri(desktop)
        return exit_code
    except subprocess.CalledProcessError as exc:
        logger.error("子程序執行失敗 (exit %s)", exc.returncode)
        return exc.returncode or 1
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        logger.error("%s", exc)
        return 1
    finally:
        stop_server(server_proc)


if __name__ == "__main__":
    raise SystemExit(main())
