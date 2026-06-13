from __future__ import annotations

import os
import sys
import uuid
from collections.abc import Callable

from events import SOURCE_LOGIC_LLM, TOPIC_CHAT_REPLY, ChatReplyEvent
from safety import SafetyFilter

from sub_llm.chat_format import cap_reply_for_chat, plain_text_for_chat
from sub_llm.config import LlmSubscriberConfig
from sub_llm.context_buffer import LiveContextBuffer
from sub_llm.llm import LlmClient
from sub_llm.startup_messages import build_degraded_startup_announcement

_STARTUP_SYSTEM_PROMPT = (
    "你是 Twitch 直播聊天室的 AI 助手，剛完成上線。"
    "請用一句有趣、親切、不油膩的繁體中文（台灣用語）向觀眾打招呼，禁止簡體字，"
    "並自然提到可以用觸發詞提問。"
    "語氣像直播間朋友，可帶一點幽默或可愛感。"
    "勿使用 Markdown，一兩句即可，正文不超過 50 字（不含 @ 標記與標點）。"
    "勿在訊息中逐字寫出觸發詞（例如 !ask），改以口語描述如何提問。"
)


def startup_announcement_enabled() -> bool:
    raw = os.environ.get("LLM_STARTUP_ANNOUNCEMENT", "true").strip().lower()
    if not raw:
        return True
    return raw in {"1", "true", "yes", "on"}


def resolve_announcement_channel() -> str:
    return (os.environ.get("TWITCH_CHANNEL") or "").strip().lstrip("#")


def build_startup_user_prompt(*, channel: str, trigger_prefixes: tuple[str, ...]) -> str:
    triggers = "、".join(trigger_prefixes) if trigger_prefixes else "!ask"
    return f"頻道名稱：{channel}。觸發詞：{triggers}。請生成上線宣告。"


def publish_startup_announcement(
    *,
    llm: LlmClient,
    safety: SafetyFilter,
    config: LlmSubscriberConfig,
    publish: Callable[[str, dict], None],
    context_buffer: LiveContextBuffer | None = None,
    backend: str | None = None,
) -> bool:
    """程序就緒後發布 LLM 生成的啟用上線訊息至 chat.reply。"""
    if not startup_announcement_enabled():
        print("[sub-llm] startup announcement disabled", file=sys.stderr, flush=True)
        return False

    channel = resolve_announcement_channel()
    if not channel:
        print(
            "[sub-llm] startup announcement skipped: TWITCH_CHANNEL not set",
            file=sys.stderr,
            flush=True,
        )
        return False

    try:
        raw_reply = llm.generate_startup_greeting(
            channel=channel,
            trigger_prefixes=tuple(config.trigger_prefixes),
        )
    except Exception as exc:
        print(
            f"[sub-llm] startup announcement LLM failed: {exc}",
            file=sys.stderr,
            flush=True,
        )
        raw_reply = build_degraded_startup_announcement(
            channel=channel,
            backend=backend,
            error=exc,
        )

    filtered_reply = safety.filter_output(plain_text_for_chat(raw_reply))
    if not filtered_reply:
        print("[sub-llm] startup announcement blocked by safety filter", file=sys.stderr, flush=True)
        return False

    filtered_reply = cap_reply_for_chat(filtered_reply, config.reply_max_length)
    if not filtered_reply:
        print("[sub-llm] startup announcement empty after length cap", file=sys.stderr, flush=True)
        return False

    correlation_id = f"startup-{uuid.uuid4().hex[:12]}"
    reply = ChatReplyEvent(
        schema_version=1,
        topic=TOPIC_CHAT_REPLY,
        platform="twitch",
        channel=channel,
        content=filtered_reply,
        reply_to_message_id=None,
        sender="bot",
        source=SOURCE_LOGIC_LLM,
        correlation_id=correlation_id,
    )
    publish(TOPIC_CHAT_REPLY, reply.to_dict())
    if context_buffer is not None:
        context_buffer.add_bot_reply(channel, filtered_reply)
    print(
        f"[sub-llm] startup announcement published channel={channel} "
        f"chars={len(filtered_reply)}",
        file=sys.stderr,
        flush=True,
    )
    return True
