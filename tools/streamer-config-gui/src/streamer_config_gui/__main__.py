"""Launch local config GUI."""

from __future__ import annotations

import argparse
import os

import uvicorn
from dotenv import load_dotenv

from streamer_config_gui.app import create_app


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Streamer 設定小工具（本機 Web）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("CONFIG_GUI_PORT", "1426")),
    )
    args = parser.parse_args(argv)

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
