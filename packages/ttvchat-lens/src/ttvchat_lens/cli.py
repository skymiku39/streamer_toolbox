"""TTVChat Lens 指令列介面。"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from .console import print_message
from .reader import ChatMessage, LiveChatReader


def _ensure_utf8_stdout() -> None:
    """確保 Windows PowerShell / cmd 終端能正確輸出 Unicode。"""
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ttvchat-lens",
        description="讀取 Twitch 直播聊天室訊息（匿名連線、無需 OAuth）",
    )
    parser.add_argument(
        "channel",
        nargs="?",
        help="Twitch 頻道名或網址（也可改用 TTVCHAT_LENS_CHANNEL 環境變數）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="將原始訊息以 JSON Lines 形式追加寫入指定檔案",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="不在終端機顯示訊息，僅寫入 --output 檔案",
    )
    parser.add_argument(
        "--nick",
        default=None,
        help="自訂 IRC nick（預設為 justinfan{random}）",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="設定 logging 等級 (預設 WARNING)",
    )
    return parser


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def run(argv: Sequence[str] | None = None) -> int:
    _ensure_utf8_stdout()
    load_dotenv()
    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)

    channel = args.channel or os.environ.get("TTVCHAT_LENS_CHANNEL")
    if not channel:
        parser.error("必須提供 channel 參數，或設定 TTVCHAT_LENS_CHANNEL 環境變數")

    reader = LiveChatReader(channel, nick=args.nick)

    output_fp = None
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output_fp = args.output.open("a", encoding="utf-8")

    def _handle(message: ChatMessage) -> None:
        if not args.quiet:
            print_message(message)
        if output_fp is not None:
            output_fp.write(json.dumps(message.to_dict(), ensure_ascii=False) + "\n")
            output_fp.flush()

    reader.on_message(_handle)

    try:
        reader.start()
    except KeyboardInterrupt:
        pass
    finally:
        if output_fp is not None:
            output_fp.close()

    return 0


if __name__ == "__main__":
    sys.exit(run())
