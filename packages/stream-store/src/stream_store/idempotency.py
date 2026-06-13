from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path


_SCHEMA = """
CREATE TABLE IF NOT EXISTS idempotency_keys (
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    claimed_at TEXT NOT NULL,
    PRIMARY KEY (namespace, key)
);

CREATE INDEX IF NOT EXISTS idx_idempotency_claimed_at
    ON idempotency_keys (claimed_at);
"""


def default_idempotency_db_path() -> str:
    raw = (
        os.environ.get("EVENT_DEDUP_DB_PATH")
        or os.environ.get("STREAM_DB_PATH")
        or "data/stream_text.db"
    )
    return str(Path(raw).expanduser().resolve())


class IdempotencyStore:
    """跨 process 的 SQLite 冪等鍵：首次 claim 成功，重複 claim 回傳 False。"""

    def __init__(
        self,
        db_path: str | Path,
        *,
        ttl_seconds: int = 86400,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._ttl_seconds = ttl_seconds
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        self._conn.close()

    def claim(self, namespace: str, key: str) -> bool:
        normalized_namespace = namespace.strip()
        normalized_key = key.strip()
        if not normalized_namespace or not normalized_key:
            return True

        self._purge_expired()
        now = datetime.now(UTC).isoformat()
        cursor = self._conn.execute(
            "INSERT OR IGNORE INTO idempotency_keys (namespace, key, claimed_at) "
            "VALUES (?, ?, ?)",
            (normalized_namespace, normalized_key, now),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def release(self, namespace: str, key: str) -> None:
        normalized_namespace = namespace.strip()
        normalized_key = key.strip()
        if not normalized_namespace or not normalized_key:
            return
        self._conn.execute(
            "DELETE FROM idempotency_keys WHERE namespace = ? AND key = ?",
            (normalized_namespace, normalized_key),
        )
        self._conn.commit()

    def _purge_expired(self) -> None:
        cutoff = (datetime.now(UTC) - timedelta(seconds=self._ttl_seconds)).isoformat()
        self._conn.execute("DELETE FROM idempotency_keys WHERE claimed_at < ?", (cutoff,))
        self._conn.commit()
