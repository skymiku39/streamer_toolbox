from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv

from app.processes.registry import register_subscriber
from bus.topology import DEFAULT_EXCHANGE, QUEUE_SHOW_OVERLAY_CHAT_MESSAGE
from sub_show_overlay.settings import LayoutMode, overlay_settings_from_env
from sub_show_overlay.subscriber import ShowOverlaySubscriber

PROCESS_NAME = "sub-show-overlay"


@register_subscriber(
    name="sub-show-overlay",
    exchange=DEFAULT_EXCHANGE,
    queue=QUEUE_SHOW_OVERLAY_CHAT_MESSAGE,
    description="chat.message → overlay HTTP + IPC",
)
def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    defaults = overlay_settings_from_env()

    parser = argparse.ArgumentParser(
        description="Subscribe chat.message → overlay HTTP + file IPC"
    )
    parser.add_argument(
        "--layout",
        choices=[mode.value for mode in LayoutMode],
        default=defaults.layout.value,
        help="Overlay layout: chat (OBS), free (desktop window IPC), or both",
    )
    parser.add_argument("--ipc-path", default=str(defaults.chat_ipc_path))
    parser.add_argument("--free-ipc-path", default=str(defaults.free_ipc_path))
    parser.add_argument("--http-host", default=defaults.http_host)
    parser.add_argument("--http-port", type=int, default=defaults.http_port)
    parser.add_argument("--max-lines", type=int, default=defaults.max_lines)
    parser.add_argument("--queue-size", type=int, default=defaults.queue_size)
    args = parser.parse_args(argv)

    settings = replace(
        defaults,
        layout=LayoutMode(args.layout),
        chat_ipc_path=Path(args.ipc_path),
        free_ipc_path=Path(args.free_ipc_path),
        http_host=args.http_host,
        http_port=args.http_port,
        max_lines=args.max_lines,
        queue_size=args.queue_size,
    )

    if settings.http_port < 1 or settings.http_port > 65535:
        print("http-port must be between 1 and 65535", file=sys.stderr)
        return 1

    subscriber = ShowOverlaySubscriber(settings)
    subscriber.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
