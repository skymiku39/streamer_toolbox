from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from stream_store.models import Summary, TextRecord

ACTIVE_SESSION_KEY = "active_session_id"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS stream_sessions (
    id TEXT PRIMARY KEY,
    channel TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS text_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    source TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    text TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT '',
    message_id TEXT NOT NULL DEFAULT '',
    summarized INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES stream_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_text_records_session_ts
    ON text_records (session_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_text_records_unsummarized
    ON text_records (session_id, summarized, timestamp);

CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    record_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES stream_sessions(id)
);

CREATE TABLE IF NOT EXISTS memory_checkpoints (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class StreamTextStore:
    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        self._conn.close()

    def ensure_session(self, session_id: str, *, channel: str) -> None:
        row = self._conn.execute(
            "SELECT id FROM stream_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is not None:
            return
        now = datetime.now(UTC).isoformat()
        self._conn.execute(
            "INSERT INTO stream_sessions (id, channel, started_at) VALUES (?, ?, ?)",
            (session_id, channel, now),
        )
        self._conn.commit()

    def append_chat(
        self,
        *,
        session_id: str,
        channel: str,
        timestamp: str,
        text: str,
        author: str,
        message_id: str,
    ) -> int:
        self.ensure_session(session_id, channel=channel)
        cursor = self._conn.execute(
            """
            INSERT INTO text_records
                (session_id, source, timestamp, text, author, channel, message_id, summarized)
            VALUES (?, 'chat', ?, ?, ?, ?, ?, 0)
            """,
            (session_id, timestamp, text, author, channel, message_id),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def append_stt(
        self,
        *,
        session_id: str,
        channel: str,
        timestamp: str,
        text: str,
        segment_id: str,
    ) -> int:
        self.ensure_session(session_id, channel=channel)
        cursor = self._conn.execute(
            """
            INSERT INTO text_records
                (session_id, source, timestamp, text, author, channel, message_id, summarized)
            VALUES (?, 'stt', ?, ?, 'streamer', ?, ?, 0)
            """,
            (session_id, timestamp, text, channel, segment_id),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def fetch_unsummarized_chat(
        self,
        session_id: str,
        *,
        limit: int = 500,
    ) -> list[TextRecord]:
        rows = self._conn.execute(
            """
            SELECT id, session_id, source, timestamp, text, author, channel, message_id
            FROM text_records
            WHERE session_id = ? AND source = 'chat' AND summarized = 0
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        return [_row_to_record(row) for row in rows]

    def fetch_unsummarized_stt(
        self,
        session_id: str,
        *,
        limit: int = 500,
    ) -> list[TextRecord]:
        rows = self._conn.execute(
            """
            SELECT id, session_id, source, timestamp, text, author, channel, message_id
            FROM text_records
            WHERE session_id = ? AND source = 'stt' AND summarized = 0
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        return [_row_to_record(row) for row in rows]

    def fetch_unsummarized_merged(
        self,
        session_id: str,
        *,
        sources: list[str],
        limit: int = 500,
    ) -> list[TextRecord]:
        if not sources:
            return []
        placeholders = ",".join("?" for _ in sources)
        rows = self._conn.execute(
            f"""
            SELECT id, session_id, source, timestamp, text, author, channel, message_id
            FROM text_records
            WHERE session_id = ? AND source IN ({placeholders}) AND summarized = 0
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (session_id, *sources, limit),
        ).fetchall()
        return [_row_to_record(row) for row in rows]

    def mark_summarized(self, record_ids: list[int]) -> None:
        if not record_ids:
            return
        placeholders = ",".join("?" for _ in record_ids)
        self._conn.execute(
            f"UPDATE text_records SET summarized = 1 WHERE id IN ({placeholders})",
            record_ids,
        )
        self._conn.commit()

    def save_summary(
        self,
        *,
        session_id: str,
        period_start: str,
        period_end: str,
        source: str,
        content: str,
        record_count: int,
    ) -> int:
        created_at = datetime.now(UTC).isoformat()
        cursor = self._conn.execute(
            """
            INSERT INTO summaries
                (session_id, period_start, period_end, source, content, created_at, record_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, period_start, period_end, source, content, created_at, record_count),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def list_summaries(self, session_id: str, *, limit: int = 20) -> list[Summary]:
        rows = self._conn.execute(
            """
            SELECT id, session_id, period_start, period_end, source, content, created_at, record_count
            FROM summaries
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        return [_row_to_summary(row) for row in rows]

    def get_checkpoint(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM memory_checkpoints WHERE key = ?",
            (key,),
        ).fetchone()
        return None if row is None else str(row["value"])

    def set_checkpoint(self, key: str, value: str) -> None:
        self._conn.execute(
            """
            INSERT INTO memory_checkpoints (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        self._conn.commit()

    def latest_session_id(self) -> str | None:
        row = self._conn.execute(
            """
            SELECT session_id FROM text_records
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        return str(row["session_id"])

    def latest_chat_session_id(self) -> str | None:
        row = self._conn.execute(
            """
            SELECT session_id FROM text_records
            WHERE source = 'chat'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        return str(row["session_id"])


def _row_to_record(row: sqlite3.Row) -> TextRecord:
    return TextRecord(
        id=int(row["id"]),
        session_id=str(row["session_id"]),
        source=str(row["source"]),
        timestamp=str(row["timestamp"]),
        text=str(row["text"]),
        author=str(row["author"]),
        channel=str(row["channel"]),
        message_id=str(row["message_id"]),
    )


def _row_to_summary(row: sqlite3.Row) -> Summary:
    return Summary(
        id=int(row["id"]),
        session_id=str(row["session_id"]),
        period_start=str(row["period_start"]),
        period_end=str(row["period_end"]),
        source=str(row["source"]),
        content=str(row["content"]),
        created_at=str(row["created_at"]),
        record_count=int(row["record_count"]),
    )
