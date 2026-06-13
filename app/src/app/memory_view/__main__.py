from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from app.console_encoding import configure_utf8_stdio
from stream_store import StreamTextStore

from app.memory_view.channel import default_channel
from app.memory_view.service import MemoryViewService

configure_utf8_stdio()


def _print_sessions(service: MemoryViewService, *, channel: str | None = None) -> None:
    active = service.resolve_active_session_id(channel=channel)
    channel_hint = f" (channel={channel})" if channel else ""
    print(f"active_session_id: {active or '—'}{channel_hint}")
    print(f"{'session_id':<28} {'channel':<16} chat  stt  summaries  pending")
    print("-" * 72)
    for session in service.list_sessions():
        marker = "*" if session.session_id == active else " "
        print(
            f"{marker}{session.session_id:<27} {session.channel:<16} "
            f"{session.chat_count:4}  {session.stt_count:4}  "
            f"{session.summary_count:9}  {session.unsummarized_count:7}"
        )


def _print_summaries(service: MemoryViewService, session_id: str, *, limit: int) -> None:
    summaries = service.list_summaries(session_id, limit=limit)
    if not summaries:
        print(f"Session {session_id!r} 尚無摘要。")
        return
    print(f"Session: {session_id}（{len(summaries)} 筆摘要）\n")
    for summary in summaries:
        print("=" * 60)
        print(
            f"#{summary.id} [{summary.source}] records={summary.record_count} "
            f"created={summary.created_at}"
        )
        print(f"period: {summary.period_start} .. {summary.period_end}")
        print(summary.content)
        print()


def main(argv: list[str] | None = None) -> int:
    load_dotenv(override=True)
    parser = argparse.ArgumentParser(description="檢視 L2 記憶摘要（summaries 表）")
    parser.add_argument(
        "--db-path",
        default=os.environ.get("STREAM_DB_PATH", "data/stream_text.db"),
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="指定 session；省略時搭配 --active 或 --list-sessions",
    )
    parser.add_argument(
        "--active",
        action="store_true",
        help="使用 checkpoint / 最新 session",
    )
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="列出所有 session 統計",
    )
    parser.add_argument(
        "--channel",
        default=None,
        help="直播間 channel（--active 時用於解析 session；預設 TWITCH_CHANNEL）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="摘要顯示上限",
    )
    args = parser.parse_args(argv)

    db_path = args.db_path
    if not os.path.isfile(db_path):
        print(f"找不到資料庫：{db_path}", file=sys.stderr)
        return 1

    store = StreamTextStore(db_path)
    service = MemoryViewService(store)
    channel = (args.channel or default_channel() or "").strip() or None
    try:
        if args.list_sessions:
            _print_sessions(service, channel=channel)
            return 0

        session_id = (args.session_id or "").strip() or None
        if args.active or session_id is None:
            session_id = service.resolve_active_session_id(channel=channel)
        if session_id is None:
            print("找不到 session；請用 --list-sessions 查看。", file=sys.stderr)
            return 1

        _print_summaries(service, session_id, limit=args.limit)
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
