from __future__ import annotations

from dataclasses import asdict

from stream_store import StreamTextStore, resolve_session_for_channel
from stream_store.models import SessionStats, Summary


class MemoryViewService:
    def __init__(self, store: StreamTextStore) -> None:
        self._store = store

    def resolve_active_session_id(self, *, channel: str | None = None) -> str | None:
        if channel:
            return resolve_session_for_channel(self._store, channel)
        return resolve_session_for_channel(self._store, "")

    def list_sessions(self, *, limit: int = 50) -> list[SessionStats]:
        return self._store.list_sessions(limit=limit)

    def list_summaries(self, session_id: str, *, limit: int = 100) -> list[Summary]:
        return self._store.list_summaries(session_id, limit=limit, ascending=True)

    def sessions_payload(self, *, revision: int = 0, channel: str | None = None) -> dict:
        active_session_id = self.resolve_active_session_id(channel=channel)
        return {
            "revision": revision,
            "active_session_id": active_session_id,
            "active_channel": channel,
            "sessions": [asdict(session) for session in self.list_sessions()],
        }

    def summaries_payload(
        self,
        session_id: str,
        *,
        revision: int = 0,
        channel: str | None = None,
    ) -> dict:
        return {
            "revision": revision,
            "session_id": session_id,
            "channel": channel,
            "summaries": [asdict(summary) for summary in self.list_summaries(session_id)],
        }
