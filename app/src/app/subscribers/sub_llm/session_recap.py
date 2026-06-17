from __future__ import annotations

import os
import re
from dataclasses import dataclass

from stream_store import StreamTextStore, resolve_session_for_channel
from sub_llm.live_activity import is_current_activity_question
from sub_llm.prompt_format import INTRA_SEP, compact_markdown, join_sections

_SESSION_RECAP = re.compile(
    r"今天|本場|這場|開台以來|整場|做了哪些|做了什麼|實現了|完成哪些|進度如何|實作了|開發了",
)

_RECAP_GUIDANCE = (
    "請依下方摘要與語音原文逐條列舉具體工作項目（工具名、功能名、開啟的軟體等）；"
    "勿以「有提到但沒詳細說／目前還不清楚」當主體回覆。"
    "若摘要與原文皆無細節，才允許一句交代。"
    "勿把觀眾暱稱當成主播名字；「今天 XXX 做了…」應指實況主本人。"
)

_RECAP_SUMMARY_SOURCES = frozenset({"chat", "stt"})


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _recap_summary_limit() -> int:
    return max(1, int(os.environ.get("LLM_SESSION_RECAP_SUMMARY_LIMIT", "30")))


def _recap_raw_stt_limit() -> int:
    return max(1, int(os.environ.get("LLM_SESSION_RECAP_RAW_STT_LIMIT", "80")))


def _recap_max_chars() -> int:
    return max(100, int(os.environ.get("LLM_SESSION_RECAP_MAX_CHARS", "8000")))


def should_enrich_session_recap(question: str) -> bool:
    """觀眾明確問及本場／今天進度時才查；一般知識題與當下實況題不查。"""
    if not _env_bool("LLM_SESSION_RECAP_ENABLED", True):
        return False
    stripped = question.strip()
    if not stripped:
        return False
    if is_current_activity_question(stripped):
        return False
    return bool(_SESSION_RECAP.search(stripped))


@dataclass(frozen=True)
class SessionRecapReference:
    text: str
    summary_count: int
    raw_stt_count: int
    qa_summary_count: int = 0


def build_session_recap_reference(
    question: str,
    *,
    channel: str,
    store: StreamTextStore | None,
    session_id: str | None = None,
) -> SessionRecapReference:
    """依問題意圖從 L2 摘要與未摘要 STT 組裝本場回顧參考（按需 enrichment）。"""
    empty = SessionRecapReference(text="", summary_count=0, raw_stt_count=0)
    if store is None or not should_enrich_session_recap(question):
        return empty

    explicit = (session_id or (os.environ.get("STREAM_SESSION_ID") or "").strip() or None)
    resolved_session = resolve_session_for_channel(
        store,
        channel,
        explicit_session_id=explicit,
    )
    if resolved_session is None:
        return empty

    all_summaries = store.list_summaries(
        resolved_session,
        limit=_recap_summary_limit(),
        ascending=True,
    )
    qa_summary_count = sum(1 for item in all_summaries if item.source == "qa")
    summaries = [
        item for item in all_summaries if item.source in _RECAP_SUMMARY_SOURCES
    ]
    stt_pending = store.fetch_unsummarized_stt(
        resolved_session,
        channel=channel or None,
        limit=_recap_raw_stt_limit(),
        recent=True,
    )
    if not summaries and not stt_pending:
        return empty

    sections: list[str] = [f"回顧:{_RECAP_GUIDANCE}"]
    if summaries:
        summary_parts = [
            f"{summary.source}:{compact_markdown(summary.content)}"
            for summary in summaries
        ]
        sections.append("摘要:" + INTRA_SEP.join(summary_parts))

    if stt_pending:
        transcript = " ".join(record.text.strip() for record in stt_pending)
        sections.append(f"語音:{transcript}")

    text = join_sections(*sections)
    max_chars = _recap_max_chars()
    if len(text) > max_chars:
        text = text[: max_chars - 3] + "..."

    return SessionRecapReference(
        text=text,
        summary_count=len(summaries),
        raw_stt_count=len(stt_pending),
        qa_summary_count=qa_summary_count,
    )
