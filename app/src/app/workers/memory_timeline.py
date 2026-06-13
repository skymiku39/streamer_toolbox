from __future__ import annotations

from stream_store.models import TextRecord


def format_chat_timeline(records: list[TextRecord]) -> str:
    """依時間排序的聊天室紀錄（每行含 timestamp）。"""
    return "\n".join(f"[{record.timestamp}] {record.author}: {record.text}" for record in records)


def format_stt_timeline(records: list[TextRecord]) -> str:
    """依時間排序的 STT 紀錄（每行含 timestamp）。"""
    return "\n".join(f"[{record.timestamp}] {record.text}" for record in records)
