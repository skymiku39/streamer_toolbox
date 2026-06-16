"""CLI：bootstrap / validate 外部設定目錄。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from streamer_config.bootstrap import ensure_layout
from streamer_config.paths import ConfigPaths, default_config_dir
from streamer_config.validate import ValidationError, validate_all


def _resolve_dir(raw: str | None) -> Path:
    if raw:
        return Path(os.path.expandvars(raw)).expanduser()
    env_dir = os.environ.get("STREAMER_CONFIG_DIR", "").strip()
    if env_dir:
        return Path(os.path.expandvars(env_dir)).expanduser()
    return default_config_dir()


def cmd_bootstrap(args: argparse.Namespace) -> int:
    channel = args.channel or os.environ.get("TWITCH_CHANNEL", "").strip() or None
    result = ensure_layout(
        _resolve_dir(args.dir),
        channel=channel,
        examples_root=Path(args.examples_root) if args.examples_root else None,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    paths = ConfigPaths.from_dir(_resolve_dir(args.dir))
    errors = validate_all(paths)
    if errors:
        for item in errors:
            print(item, file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, "paths": paths.to_dict()}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="streamer-config: 外部設定目錄工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser("bootstrap", help="建立設定目錄並複製範例（不覆寫）")
    bootstrap.add_argument(
        "--dir", help="設定目錄（預設 STREAMER_CONFIG_DIR 或 ~/streamer-config）"
    )
    bootstrap.add_argument("--channel", help="Twitch 頻道名（用於 knowledge/{channel}.md）")
    bootstrap.add_argument(
        "--examples-root",
        help="repo 根目錄（預設自動偵測）",
    )
    bootstrap.set_defaults(func=cmd_bootstrap)

    validate = subparsers.add_parser("validate", help="驗證設定目錄內 JSON")
    validate.add_argument("--dir", help="設定目錄（預設 STREAMER_CONFIG_DIR 或 ~/streamer-config）")
    validate.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ValidationError as exc:
        for item in exc.errors:
            print(item, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
