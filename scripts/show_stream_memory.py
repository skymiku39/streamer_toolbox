# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    db = Path("data/stream_text.db")
    if not db.exists():
        print("找不到 data/stream_text.db，請先執行抓取流程。")
        return

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    sessions = conn.execute(
        """
        SELECT session_id, COUNT(*) AS n
        FROM text_records
        WHERE session_id LIKE 'caren_surfdemon%'
        GROUP BY session_id
        ORDER BY session_id DESC
        """
    ).fetchall()

    if not sessions:
        print("尚無 caren_surfdemon 的聊天記錄。")
        conn.close()
        return

    for sess in sessions:
        sid = sess["session_id"]
        print("=" * 60)
        print(f"Session: {sid}  （共 {sess['n']} 則）")
        print("=" * 60)
        print("\n【聊天記錄 text_records】\n")
        for row in conn.execute(
            """
            SELECT id, timestamp, author, text, summarized
            FROM text_records
            WHERE session_id = ?
            ORDER BY id
            """,
            (sid,),
        ):
            flag = "已摘要" if row["summarized"] else "未摘要"
            print(f"#{row['id']} [{flag}] {row['timestamp']}")
            print(f"  {row['author']}: {row['text']}")
            print()

        print("【記憶摘要 summaries】\n")
        summaries = conn.execute(
            """
            SELECT id, period_start, period_end, record_count, content, created_at
            FROM summaries
            WHERE session_id = ?
            ORDER BY id
            """,
            (sid,),
        ).fetchall()
        if not summaries:
            print("  （尚無摘要，可執行 uv run sub-memory-worker --once）\n")
        for s in summaries:
            print(f"Summary #{s['id']}  records={s['record_count']}")
            print(f"  期間: {s['period_start']} ~ {s['period_end']}")
            print(f"  建立: {s['created_at']}")
            print(f"  內容:\n{s['content']}")
            print()

    cp = conn.execute(
        "SELECT value FROM memory_checkpoints WHERE key = 'active_session_id'"
    ).fetchone()
    print("=" * 60)
    print(f"目前 checkpoint (active_session_id): {cp['value'] if cp else '—'}")
    conn.close()


if __name__ == "__main__":
    main()
