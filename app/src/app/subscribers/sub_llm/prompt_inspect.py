"""!ask prompt 乾跑檢視：組裝與 handler 相同的檢索結果，不呼叫 LLM。

供人工或 AI 助手檢視 prompt 品質，驗證記憶／RAG 是否命中預期。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from events import TOPIC_CHAT_MESSAGE, TOPIC_STT_SEGMENT, ChatMessageEvent, SttSegmentEvent
from stream_store import StreamTextStore

from sub_llm.context_buffer import LiveContextBuffer
from sub_llm.game_context import build_game_reference, create_game_info_provider, resolve_live_game_name
from sub_llm.knowledge import KnowledgeStore
from sub_llm.live_activity import current_activity_context_hint, is_current_activity_question
from sub_llm.prompt_assembly import analyze_prompt_payload, build_ask_messages
from sub_llm.prompt_format import join_lines
from sub_llm.session_recap import build_session_recap_reference
from sub_llm.short_term_rag import ShortTermRagStore

_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[a-zA-Z0-9]{2,}")
_LAYER_MARKER_KEYS = {
    "stt": "has_stt_marker",
    "chat": "has_chat_marker",
    "stream": "has_stream_metadata_marker",
    "static_kb": "has_static_kb_marker",
    "memory": "has_memory_marker",
    "bot_memory": "has_memory_marker",
    "game": "has_game_reference_marker",
    "session_recap": "has_session_recap_marker",
}


@dataclass(frozen=True)
class AskInputs:
    context: str
    knowledge: str
    game_reference: str
    session_recap_reference: str
    short_term_hit: bool = False


@dataclass(frozen=True)
class AskInspectResult:
    question: str
    channel: str
    inputs: AskInputs
    analysis: dict[str, Any]
    relevance: float
    warnings: tuple[str, ...]
    messages: list[dict[str, str]]
    score: float

    @property
    def passed(self) -> bool:
        return not self.warnings and self.score >= 0.6


@dataclass(frozen=True)
class InspectCase:
    question: str
    channel: str = ""
    expect: tuple[str, ...] = ()
    expect_layers: tuple[str, ...] = ()
    any_of: bool = False
    label: str = ""
    expected_info: str = ""


@dataclass
class InspectCaseResult:
    case: InspectCase
    inspect: AskInspectResult
    found: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    layer_hits: dict[str, bool] = field(default_factory=dict)
    layer_missing: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        fragment_ok = True
        if self.case.expect:
            if self.case.any_of:
                fragment_ok = bool(self.found)
            else:
                fragment_ok = not self.missing
        layer_ok = not self.layer_missing
        return fragment_ok and layer_ok


def _question_tokens(question: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(token.casefold() for token in _TOKEN_RE.findall(question)))


def _relevance_score(question: str, *blobs: str) -> float:
    tokens = _question_tokens(question)
    if not tokens:
        return 0.0
    haystack = "\n".join(blob for blob in blobs if blob).casefold()
    if not haystack:
        return 0.0
    hits = sum(1 for token in tokens if token in haystack)
    return hits / len(tokens)


def _layer_flags(analysis: dict[str, Any]) -> dict[str, bool]:
    return {
        layer: bool(analysis.get(marker, False))
        for layer, marker in _LAYER_MARKER_KEYS.items()
    }


def _collect_warnings(
    question: str,
    *,
    inputs: AskInputs,
    analysis: dict[str, Any],
    relevance: float,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if analysis["context_len"] == 0 and analysis["knowledge_len"] == 0:
        warnings.append("context 與 knowledge 皆為空，LLM 僅能依通識作答")
    if relevance < 0.2 and inputs.knowledge.strip():
        warnings.append(f"問題與檢索內容關鍵字重疊偏低（relevance={relevance:.2f}）")
    if is_current_activity_question(question) and not analysis["has_stt_marker"]:
        warnings.append("當下實況題但 prompt 無逐字稿標記")
    if "今天" in question or "本場" in question:
        if not analysis["has_session_recap_marker"] and not analysis["has_memory_marker"]:
            warnings.append("本場進度題但無回顧摘要或長期記憶標記")
    return tuple(warnings)


def _score_inspection(
    *,
    analysis: dict[str, Any],
    relevance: float,
    warnings: tuple[str, ...],
) -> float:
    injected = 0
    if analysis["context_len"] > 0:
        injected += 1
    if analysis["knowledge_len"] > 0:
        injected += 1
    if analysis["has_game_reference_marker"]:
        injected += 1
    if analysis["has_session_recap_marker"]:
        injected += 1
    coverage = injected / 4
    penalty = min(0.5, 0.1 * len(warnings))
    return max(0.0, min(1.0, 0.45 * coverage + 0.45 * relevance + 0.1 - penalty))


def assemble_ask_inputs(
    question: str,
    *,
    channel: str,
    context_buffer: LiveContextBuffer,
    knowledge_store: KnowledgeStore,
    stream_store: StreamTextStore | None = None,
    short_term_rag: ShortTermRagStore | None = None,
    game_info=None,
) -> AskInputs:
    """與 LlmSubscriber._handle_chat_message 相同的檢索組裝，但不呼叫 LLM。"""
    stt_count, _chat_count, _bot_reply_count, _context_len, _has_stream = context_buffer.stats(
        channel
    )
    context = context_buffer.context_text(channel)
    if is_current_activity_question(question):
        context = join_lines(
            context,
            current_activity_context_hint(has_stt=stt_count > 0),
        )
    elif stt_count == 0:
        context = join_lines(
            context,
            current_activity_context_hint(has_stt=False),
        )

    knowledge = knowledge_store.query(question, channel=channel)
    short_term_hit = False
    if short_term_rag is not None:
        short_term = short_term_rag.query(
            channel,
            question,
            exclude_questions=context_buffer.recent_bot_questions(channel),
        )
        if short_term:
            short_term_hit = True
            knowledge = f"{short_term}\n{knowledge}" if knowledge else short_term

    provider = game_info if game_info is not None else create_game_info_provider()
    live_game = resolve_live_game_name(context_buffer, channel)
    game_reference = build_game_reference(
        question,
        game_name=live_game,
        provider=provider,
    )
    session_recap = build_session_recap_reference(
        question,
        channel=channel,
        store=stream_store,
    )
    return AskInputs(
        context=context,
        knowledge=knowledge,
        game_reference=game_reference,
        session_recap_reference=session_recap.text,
        short_term_hit=short_term_hit,
    )


def inspect_ask_prompt(
    question: str,
    *,
    channel: str,
    inputs: AskInputs,
) -> AskInspectResult:
    analysis = analyze_prompt_payload(
        question,
        context=inputs.context,
        knowledge=inputs.knowledge,
        game_reference=inputs.game_reference,
        session_recap_reference=inputs.session_recap_reference,
    )
    messages = analysis.pop("messages")
    relevance = _relevance_score(
        question,
        inputs.context,
        inputs.knowledge,
        inputs.game_reference,
        inputs.session_recap_reference,
    )
    warnings = _collect_warnings(question, inputs=inputs, analysis=analysis, relevance=relevance)
    score = _score_inspection(analysis=analysis, relevance=relevance, warnings=warnings)
    return AskInspectResult(
        question=question,
        channel=channel,
        inputs=inputs,
        analysis=analysis,
        relevance=relevance,
        warnings=warnings,
        messages=messages,
        score=score,
    )


def hydrate_context_from_db(
    buffer: LiveContextBuffer,
    store: StreamTextStore,
    channel: str,
    *,
    window_minutes: int,
) -> int:
    """從 SQLite 載入近期 chat/stt 至 context buffer；回傳載入筆數。"""
    session_id = store.latest_session_id_for_channel(channel) or store.latest_session_id()
    if not session_id:
        return 0
    cutoff = datetime.now(UTC) - timedelta(minutes=max(1, window_minutes))
    loaded = 0
    for record in store.fetch_unsummarized_merged(
        session_id,
        sources=["chat", "stt"],
        channel=channel or None,
        limit=500,
    ):
        try:
            ts = datetime.fromisoformat(record.timestamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if ts < cutoff:
            continue
        if record.source == "stt":
            buffer.add_segment(
                SttSegmentEvent(
                    schema_version=1,
                    topic=TOPIC_STT_SEGMENT,
                    platform="twitch",
                    channel=channel or record.channel,
                    segment_id=record.message_id or f"db-stt-{record.id}",
                    text=record.text,
                    timestamp=record.timestamp,
                )
            )
            loaded += 1
        elif record.source == "chat":
            buffer.add_chat_message(
                ChatMessageEvent(
                    schema_version=1,
                    topic=TOPIC_CHAT_MESSAGE,
                    platform="twitch",
                    message_id=record.message_id or f"db-chat-{record.id}",
                    author_name=record.author or "viewer",
                    author_id="",
                    content=record.text,
                    timestamp=record.timestamp,
                    channel=channel or record.channel,
                )
            )
            loaded += 1
    return loaded


def evaluate_inspect_cases(
    inspect_fn,
    cases: list[InspectCase],
) -> list[InspectCaseResult]:
    results: list[InspectCaseResult] = []
    for case in cases:
        inspect = inspect_fn(case.question, case.channel)
        haystack = "\n".join(
            (
                inspect.inputs.context,
                inspect.inputs.knowledge,
                inspect.inputs.game_reference,
                inspect.inputs.session_recap_reference,
            )
        ).casefold()
        found = tuple(piece for piece in case.expect if piece.casefold() in haystack)
        missing = tuple(piece for piece in case.expect if piece.casefold() not in haystack)
        layer_flags = _layer_flags(inspect.analysis)
        layer_hits = {layer: layer_flags.get(layer, False) for layer in case.expect_layers}
        layer_missing = tuple(layer for layer, hit in layer_hits.items() if not hit)
        results.append(
            InspectCaseResult(
                case=case,
                inspect=inspect,
                found=found,
                missing=missing,
                layer_hits=layer_hits,
                layer_missing=layer_missing,
            )
        )
    return results


def load_inspect_cases(path: str | Path) -> list[InspectCase]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("ask inspect 案例集必須是 JSON 陣列")
    cases: list[InspectCase] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 筆案例必須是物件")
        question = str(item.get("question", "")).strip()
        if not question:
            raise ValueError(f"第 {index} 筆案例缺少 question")
        cases.append(
            InspectCase(
                question=question,
                channel=str(item.get("channel", "")),
                expect=tuple(str(piece) for piece in (item.get("expect") or [])),
                expect_layers=tuple(str(layer) for layer in (item.get("expect_layers") or [])),
                any_of=bool(item.get("any_of", False)),
                label=str(item.get("label", "")),
                expected_info=str(item.get("expected_info", "")),
            )
        )
    return cases


def format_inspection_report(result: AskInspectResult, *, include_prompt: bool = False) -> str:
    lines = [
        f"=== ask inspect | {result.channel!r} | {result.question!r} ===",
        f"score={result.score:.2f} relevance={result.relevance:.2f} passed={result.passed}",
        (
            "layers: "
            f"stt={result.analysis['has_stt_marker']} "
            f"chat={result.analysis['has_chat_marker']} "
            f"stream={result.analysis['has_stream_metadata_marker']} "
            f"static_kb={result.analysis['has_static_kb_marker']} "
            f"memory={result.analysis['has_memory_marker']} "
            f"game={result.analysis['has_game_reference_marker']} "
            f"recap={result.analysis['has_session_recap_marker']}"
        ),
        (
            "sizes: "
            f"context={result.analysis['context_len']} "
            f"reference={result.analysis['knowledge_len']} "
            f"short_term_hit={result.inputs.short_term_hit}"
        ),
    ]
    if result.warnings:
        lines.append("warnings:")
        lines.extend(f"  - {warning}" for warning in result.warnings)
    if include_prompt:
        system = next(m["content"] for m in result.messages if m["role"] == "system")
        user = next(m["content"] for m in result.messages if m["role"] == "user")
        lines.append("--- system prompt ---")
        lines.append(system)
        lines.append("--- user prompt ---")
        lines.append(user)
    return "\n".join(lines)


def format_case_report(results: list[InspectCaseResult]) -> str:
    lines: list[str] = []
    passed = 0
    for item in results:
        status = "PASS" if item.passed else "FAIL"
        if item.passed:
            passed += 1
        label = item.case.label or item.case.question
        lines.append(
            f"[{status}] score={item.inspect.score:.2f} "
            f"relevance={item.inspect.relevance:.2f} {label!r}"
        )
        if item.case.expected_info:
            lines.append(f"        expect: {item.case.expected_info}")
        if item.missing:
            lines.append(f"        missing_fragments={list(item.missing)}")
        if item.layer_missing:
            lines.append(f"        missing_layers={list(item.layer_missing)}")
        for warning in item.inspect.warnings:
            lines.append(f"        warn: {warning}")
    total = len(results)
    rate = passed / total if total else 1.0
    lines.append(f"-- pass_rate={rate:.3f} ({passed}/{total})")
    return "\n".join(lines)
