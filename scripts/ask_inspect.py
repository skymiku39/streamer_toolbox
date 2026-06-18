"""!ask 乾跑：組裝 prompt 並分析記憶／RAG 品質，不呼叫 LLM。

與 sub-llm handler 使用相同檢索路徑（Chroma、短期 RAG、遊戲資料、本場回顧），
輸出結構化報告供人工或 AI 助手檢視 prompt 是否含預期上下文。

用法：
    uv run python scripts/ask_inspect.py "誰是 LNG"
    uv run python scripts/ask_inspect.py "主播在玩什麼" --from-db --full
    uv run python scripts/ask_inspect.py --cases scripts/eval/ask_inspect_cases.json
    uv run python scripts/ask_inspect.py "777 幸運數字" --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
for rel in ("app/src", "app/src/app/subscribers"):
    candidate = ROOT / rel
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

load_dotenv(ROOT / ".env")

from events import (  # noqa: E402
    TOPIC_CHAT_MESSAGE,
    TOPIC_STT_SEGMENT,
    ChatMessageEvent,
    SttSegmentEvent,
)
from sub_llm.context_buffer import LiveContextBuffer  # noqa: E402
from sub_llm.factory import (  # noqa: E402
    create_knowledge_store,
    create_stream_text_store,
    preload_knowledge_store,
)
from sub_llm.game_context import create_game_info_provider  # noqa: E402
from sub_llm.prompt_inspect import (  # noqa: E402
    assemble_ask_inputs,
    evaluate_inspect_cases,
    format_case_report,
    format_inspection_report,
    hydrate_context_from_db,
    inspect_ask_prompt,
    load_inspect_cases,
)
from sub_llm.short_term_rag import ShortTermRagStore  # noqa: E402

DEFAULT_CASES = ROOT / "scripts" / "eval" / "ask_inspect_cases.json"


def _default_channel() -> str:
    return (os.environ.get("TWITCH_CHANNEL") or "skymiku39").strip()


def _build_context_buffer(*, sample: bool, channel: str) -> LiveContextBuffer:
    bot_id = (os.environ.get("TWITCH_BOT_ID") or "").strip()
    skip_ids = frozenset({bot_id}) if bot_id else frozenset()
    window = int(os.environ.get("LLM_CONTEXT_WINDOW_MINUTES", "5"))
    bot_window = int(os.environ.get("LLM_BOT_REPLY_WINDOW_MINUTES", "30"))
    bot_pairs = int(os.environ.get("LLM_BOT_REPLY_MAX_PAIRS", "5"))
    buffer = LiveContextBuffer(
        window_minutes=window,
        skip_author_ids=skip_ids,
        bot_reply_window_minutes=bot_window,
        bot_reply_max_pairs=bot_pairs,
    )
    if not sample:
        return buffer

    from datetime import UTC, datetime

    now = datetime.now(UTC).isoformat()
    buffer.add_segment(
        SttSegmentEvent(
            schema_version=1,
            topic=TOPIC_STT_SEGMENT,
            platform="twitch",
            channel=channel,
            segment_id="inspect-stt-1",
            text="主播正在測試 AI 機器人與直播摘要系統",
            timestamp=now,
            start_sec=120.0,
        )
    )
    buffer.add_chat_message(
        ChatMessageEvent(
            schema_version=1,
            topic=TOPIC_CHAT_MESSAGE,
            platform="twitch",
            message_id="inspect-chat-1",
            author_name="豆腐還沒",
            author_id="viewer-1",
            content="LNG Live 是台灣實況團體",
            timestamp=now,
            channel=channel,
        )
    )
    return buffer


def _build_short_term_rag() -> ShortTermRagStore | None:
    enabled = (os.environ.get("LLM_SHORT_TERM_RAG_ENABLED", "true") or "true").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return None
    return ShortTermRagStore(
        window_minutes=int(os.environ.get("LLM_SHORT_TERM_RAG_MINUTES", "30")),
        max_pairs=int(os.environ.get("LLM_SHORT_TERM_RAG_MAX_PAIRS", "20")),
    )


def _inspect_one(
    question: str,
    *,
    channel: str,
    context_buffer: LiveContextBuffer,
    knowledge_store,
    stream_store,
    short_term_rag: ShortTermRagStore | None,
    game_info,
):
    inputs = assemble_ask_inputs(
        question,
        channel=channel,
        context_buffer=context_buffer,
        knowledge_store=knowledge_store,
        stream_store=stream_store,
        short_term_rag=short_term_rag,
        game_info=game_info,
    )
    return inspect_ask_prompt(question, channel=channel, inputs=inputs)


def _result_to_json(result) -> dict:
    return {
        "question": result.question,
        "channel": result.channel,
        "score": result.score,
        "relevance": result.relevance,
        "passed": result.passed,
        "warnings": list(result.warnings),
        "analysis": {k: v for k, v in result.analysis.items()},
        "inputs": {
            "context_len": len(result.inputs.context),
            "knowledge_len": len(result.inputs.knowledge),
            "game_reference_len": len(result.inputs.game_reference),
            "session_recap_len": len(result.inputs.session_recap_reference),
            "short_term_hit": result.inputs.short_term_hit,
        },
        "messages": result.messages,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="!ask 乾跑：檢視 prompt 與記憶／RAG 品質")
    parser.add_argument("question", nargs="?", help="單題問題（與 --cases 二擇一）")
    parser.add_argument("--channel", default=None, help="Twitch 頻道（預設 TWITCH_CHANNEL）")
    parser.add_argument("--cases", type=Path, default=None, help="批次案例 JSON 路徑")
    parser.add_argument(
        "--sample-context",
        action="store_true",
        help="注入範例 STT／聊天（無 --from-db 時僅用空 context）",
    )
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="從 stream_text.db 載入近期 chat/stt 至 context buffer",
    )
    parser.add_argument("--full", action="store_true", help="輸出完整 system/user prompt")
    parser.add_argument("--json", action="store_true", help="以 JSON 輸出（方便 AI 助手分析）")
    parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=None,
        help="批次模式：pass_rate 低於門檻則非零結束",
    )
    args = parser.parse_args(argv)

    channel = (args.channel or _default_channel()).strip()
    knowledge_store = create_knowledge_store()
    preload_knowledge_store(knowledge_store)
    stream_store = create_stream_text_store()
    short_term_rag = _build_short_term_rag()
    game_info = create_game_info_provider()

    context_buffer = _build_context_buffer(sample=args.sample_context, channel=channel)
    if args.from_db:
        loaded = hydrate_context_from_db(
            context_buffer,
            stream_store,
            channel,
            window_minutes=int(os.environ.get("LLM_CONTEXT_WINDOW_MINUTES", "5")),
        )
        print(f"[ask-inspect] hydrated {loaded} records from {stream_store.path}", file=sys.stderr)

    inspect_fn = lambda question, case_channel: _inspect_one(  # noqa: E731
        question,
        channel=case_channel or channel,
        context_buffer=context_buffer,
        knowledge_store=knowledge_store,
        stream_store=stream_store,
        short_term_rag=short_term_rag,
        game_info=game_info,
    )

    if args.cases is not None:
        cases_path = args.cases
    elif args.question is None:
        cases_path = DEFAULT_CASES
    else:
        cases_path = None

    if cases_path is not None:
        cases = load_inspect_cases(cases_path)
        if not cases:
            print("案例集為空", file=sys.stderr)
            return 2
        results = evaluate_inspect_cases(inspect_fn, cases)
        if args.json:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            payload = [
                {
                    "label": item.case.label,
                    "expected_info": item.case.expected_info,
                    "question": item.case.question,
                    "passed": item.passed,
                    "found": list(item.found),
                    "missing": list(item.missing),
                    "layer_missing": list(item.layer_missing),
                    **_result_to_json(item.inspect),
                }
                for item in results
            ]
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(format_case_report(results))
            if args.full:
                for item in results:
                    print()
                    print(format_inspection_report(item.inspect, include_prompt=True))
        pass_rate = sum(1 for item in results if item.passed) / len(results)
        if args.min_pass_rate is not None and pass_rate < args.min_pass_rate:
            print(
                f"pass_rate {pass_rate:.3f} 低於門檻 {args.min_pass_rate:.3f}",
                file=sys.stderr,
            )
            return 1
        return 0

    if not args.question:
        parser.error("請提供 question 或 --cases")

    result = inspect_fn(args.question, channel)
    if args.json:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(_result_to_json(result), ensure_ascii=False, indent=2))
    else:
        print(format_inspection_report(result, include_prompt=args.full))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
