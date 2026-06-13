"""驗證 !ask 實際組裝的 LLM prompt 是否含各層記憶（讀取 .env 與本機資料）。"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [
    str(ROOT / "app" / "src"),
    str(ROOT / "app" / "src" / "app" / "subscribers"),
]

load_dotenv(ROOT / ".env")

from events import TOPIC_CHAT_MESSAGE, TOPIC_STT_SEGMENT, ChatMessageEvent, SttSegmentEvent  # noqa: E402
from sub_llm.context_buffer import LiveContextBuffer  # noqa: E402
from sub_llm.factory import create_knowledge_store, preload_knowledge_store  # noqa: E402
from sub_llm.prompt_assembly import analyze_prompt_payload  # noqa: E402


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_sample_context(channel: str) -> tuple[LiveContextBuffer, tuple[int, int, int]]:
    bot_id = (os.environ.get("TWITCH_BOT_ID") or "").strip()
    skip_ids = frozenset({bot_id}) if bot_id else frozenset()
    window = int(os.environ.get("LLM_CONTEXT_WINDOW_MINUTES", "5"))
    buffer = LiveContextBuffer(window_minutes=window, skip_author_ids=skip_ids)

    buffer.add_segment(
        SttSegmentEvent(
            schema_version=1,
            topic=TOPIC_STT_SEGMENT,
            platform="twitch",
            channel=channel,
            segment_id="verify-stt-1",
            text="主播正在測試 AI 機器人與直播摘要系統",
            timestamp=_now_iso(),
            start_sec=120.0,
        )
    )
    buffer.add_chat_message(
        ChatMessageEvent(
            schema_version=1,
            topic=TOPIC_CHAT_MESSAGE,
            platform="twitch",
            message_id="verify-chat-1",
            author_name="豆腐還沒",
            author_id="viewer-1",
            content="LNG Live 是台灣實況團體",
            timestamp=_now_iso(),
            channel=channel,
        )
    )
    return buffer, buffer.stats(channel)


def main() -> int:
    channel = (os.environ.get("TWITCH_CHANNEL") or "skymiku39").strip()
    knowledge_path = os.environ.get("LLM_KNOWLEDGE_PATH", "data/knowledge")

    store = create_knowledge_store(knowledge_path or None)
    preload_knowledge_store(store)

    context_buffer, (stt_count, chat_count, context_len) = _build_sample_context(channel)
    context = context_buffer.context_text(channel)

    scenarios = [
        ("777 幸運數字", "靜態知識庫"),
        ("主播在玩什麼", "長期摘要記憶"),
        ("誰是 LNG", "混合檢索"),
    ]

    report: dict = {
        "channel": channel,
        "backend": os.environ.get("LLM_KNOWLEDGE_BACKEND"),
        "memory_from_db": os.environ.get("LLM_MEMORY_FROM_DB"),
        "buffer_stats": {"stt": stt_count, "chat": chat_count, "context_len": context_len},
        "scenarios": [],
    }

    all_ok = True
    for question, label in scenarios:
        knowledge = store.query(question, channel=channel)
        analysis = analyze_prompt_payload(question, context=context, knowledge=knowledge)
        scenario = {
            "label": label,
            "question": question,
            "knowledge_len": len(knowledge),
            "analysis": {k: v for k, v in analysis.items() if k != "messages"},
        }
        report["scenarios"].append(scenario)

        checks = {
            "context_injected": analysis["context_len"] > 0,
            "knowledge_injected": analysis["knowledge_len"] > 0,
            "stt_marker": analysis["has_stt_marker"],
            "chat_marker": analysis["has_chat_marker"],
            "general_knowledge_hint": analysis["has_general_knowledge_hint"],
        }
        if label == "靜態知識庫":
            checks["static_kb"] = analysis["has_static_kb_marker"]
        if label in {"長期摘要記憶", "混合檢索"}:
            checks["memory_rag"] = analysis["has_memory_marker"]

        scenario["checks"] = checks
        if not all(checks.values()):
            all_ok = False

        print(f"\n=== {label} | {question} ===")
        print(json.dumps(checks, ensure_ascii=False, indent=2))
        user_msg = next(m["content"] for m in analysis["messages"] if m["role"] == "user")
        print("--- user prompt preview (first 600 chars) ---")
        print(user_msg[:600])

    log_path = ROOT.parent / "game" / "skymiku" / "story" / "debug-23008d.log"
    if not log_path.parent.is_dir():
        log_path = ROOT / "debug-prompt-verify.log"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "prompt_verify", **report}, ensure_ascii=False) + "\n")

    print(f"\n[verify] report appended to {log_path}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
