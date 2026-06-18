from __future__ import annotations

import os
from dataclasses import dataclass

from stream_store.session import resolve_session_id as build_session_id


@dataclass(frozen=True)
class RecordConfig:
    db_path: str
    session_id: str | None
    record_mode: str

    @classmethod
    def from_env(cls) -> RecordConfig:
        mode = (os.environ.get("RECORD_MODE", "chat") or "chat").strip().lower()
        return cls(
            db_path=os.environ.get("STREAM_DB_PATH", "data/stream_text.db"),
            session_id=(os.environ.get("STREAM_SESSION_ID") or "").strip() or None,
            record_mode=mode,
        )

    def validate(self) -> None:
        if self.record_mode not in {"chat", "stt", "both"}:
            raise ValueError(f"unsupported RECORD_MODE: {self.record_mode!r}")

    @property
    def include_chat(self) -> bool:
        return self.record_mode in {"chat", "both"}

    @property
    def include_stt(self) -> bool:
        return self.record_mode in {"stt", "both"}


def routing_keys_for_mode(record_mode: str) -> list[str]:
    from events import TOPIC_CHAT_MESSAGE, TOPIC_STT_SEGMENT

    config = RecordConfig(db_path="", session_id=None, record_mode=record_mode)
    config.validate()
    keys: list[str] = []
    if config.include_chat:
        keys.append(TOPIC_CHAT_MESSAGE)
    if config.include_stt:
        keys.append(TOPIC_STT_SEGMENT)
    return keys


def resolve_session_id(config: RecordConfig, *, channel: str) -> str:
    return build_session_id(
        channel=channel,
        explicit_session_id=config.session_id,
    )
