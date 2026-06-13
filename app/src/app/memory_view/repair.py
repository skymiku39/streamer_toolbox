from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from stream_store import StreamTextStore
from stream_store.session import normalize_channel


@dataclass(frozen=True)
class SessionRepairReport:
    session_id: str
    channel: str
    migrated_record_ids: list[int]
    deleted_summary_ids: list[int]
    reset_chat_record_ids: list[int]


def _session_id_for_record(channel: str, timestamp: str) -> str:
    normalized = normalize_channel(channel)
    day = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%Y%m%d")
    return f"{normalized}_{day}"


def find_cross_channel_record_ids(
    store: StreamTextStore,
    session_id: str,
    *,
    channel: str,
) -> list[int]:
    expected = normalize_channel(channel)
    rows = store._conn.execute(
        """
        SELECT id, channel FROM text_records
        WHERE session_id = ?
          AND LOWER(REPLACE(channel, '#', '')) != ?
        """,
        (session_id, expected),
    ).fetchall()
    return [int(row["id"]) for row in rows]


def find_contaminated_chat_summary_ids(
    store: StreamTextStore,
    session_id: str,
    *,
    channel: str,
) -> list[int]:
    expected = normalize_channel(channel)
    summaries = store.list_summaries(session_id, limit=500, ascending=True)
    contaminated: list[int] = []
    for summary in summaries:
        if summary.source != "chat":
            continue
        row = store._conn.execute(
            """
            SELECT COUNT(*) AS n FROM text_records
            WHERE session_id = ?
              AND source = 'chat'
              AND timestamp >= ?
              AND timestamp <= ?
              AND LOWER(REPLACE(channel, '#', '')) != ?
            """,
            (session_id, summary.period_start, summary.period_end, expected),
        ).fetchone()
        if row and int(row["n"]) > 0:
            contaminated.append(summary.id)
    return contaminated


def repair_session_channel_isolation(
    store: StreamTextStore,
    session_id: str,
    *,
    channel: str,
    delete_summary_ids: list[int] | None = None,
    preserve_summarized_chat_ids: list[int] | None = None,
) -> SessionRepairReport:
    """修正 session 內跨 channel 混寫：遷移錯誤紀錄、刪除混料摘要、重置待重摘要旗標。"""
    normalized = normalize_channel(channel)

    contaminated = find_contaminated_chat_summary_ids(
        store, session_id, channel=normalized
    )
    to_delete = sorted(set(contaminated) | set(delete_summary_ids or []))

    migrated: list[int] = []
    cross_ids = find_cross_channel_record_ids(store, session_id, channel=normalized)
    for record_id in cross_ids:
        row = store._conn.execute(
            "SELECT channel, timestamp FROM text_records WHERE id = ?",
            (record_id,),
        ).fetchone()
        if row is None:
            continue
        target_session = _session_id_for_record(str(row["channel"]), str(row["timestamp"]))
        store.ensure_session(target_session, channel=str(row["channel"]))
        store.relocate_records([record_id], target_session_id=target_session)
        store.unmark_summarized([record_id])
        migrated.append(record_id)

    deleted: list[int] = []
    for summary_id in to_delete:
        if store.delete_summary(summary_id):
            deleted.append(summary_id)

    preserve = set(preserve_summarized_chat_ids or [])
    rows = store._conn.execute(
        """
        SELECT id FROM text_records
        WHERE session_id = ?
          AND source = 'chat'
          AND LOWER(REPLACE(channel, '#', '')) = ?
          AND summarized = 1
        """,
        (session_id, normalized),
    ).fetchall()
    reset_ids = [int(row["id"]) for row in rows if int(row["id"]) not in preserve]
    store.unmark_summarized(reset_ids)

    return SessionRepairReport(
        session_id=session_id,
        channel=normalized,
        migrated_record_ids=migrated,
        deleted_summary_ids=deleted,
        reset_chat_record_ids=reset_ids,
    )
