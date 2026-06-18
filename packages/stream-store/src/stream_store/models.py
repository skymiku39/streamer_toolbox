from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextRecord:
    id: int
    session_id: str
    source: str
    timestamp: str
    text: str
    author: str
    channel: str
    message_id: str


@dataclass(frozen=True)
class Summary:
    id: int
    session_id: str
    period_start: str
    period_end: str
    source: str
    content: str
    created_at: str
    record_count: int
    category: str = ""


@dataclass(frozen=True)
class SessionStats:
    session_id: str
    channel: str
    chat_count: int
    stt_count: int
    summary_count: int
    unsummarized_count: int
