from __future__ import annotations

from pkg_stream_store.models import TextRecord


def format_merged_timeline(records: list[TextRecord]) -> str:
    """依時間排序，標記 [CHAT] 觀眾與 [STT] 實況主語音。"""
    lines: list[str] = []
    for record in records:
        if record.source == "chat":
            lines.append(f"[{record.timestamp}] [CHAT] {record.author}: {record.text}")
        elif record.source == "stt":
            lines.append(f"[{record.timestamp}] [STT] {record.text}")
        else:
            lines.append(f"[{record.timestamp}] [{record.source.upper()}] {record.text}")
    return "\n".join(lines)


def pair_qa_candidates(records: list[TextRecord]) -> list[tuple[TextRecord, TextRecord | None]]:
    """規則版問答配對：觀眾訊息後的第一段 STT 視為回應候選。"""
    pairs: list[tuple[TextRecord, TextRecord | None]] = []
    index = 0
    while index < len(records):
        record = records[index]
        if record.source != "chat":
            index += 1
            continue
        answer: TextRecord | None = None
        for candidate in records[index + 1 :]:
            if candidate.source == "stt":
                answer = candidate
                break
            if candidate.source == "chat":
                break
        pairs.append((record, answer))
        index += 1
    return pairs
