from __future__ import annotations

import sys
from typing import Any

from events import SOURCE_LOGIC_LLM, TOPIC_CHAT_REPLY, ChatReplyEvent
from stream_store import StreamTextStore, set_active_session_for_channel

from app.subscribers.stream_record_config import RecordConfig, resolve_session_id


class BatchQaMemoryWriter:
    """將 logic-llm 的 chat.reply 寫入 text_records，供 L2 定時摘要（無額外 LLM）。"""

    def handle(self, payload: dict[str, Any]) -> bool:
        if payload.get("topic") != TOPIC_CHAT_REPLY:
            return False

        event = ChatReplyEvent.from_dict(payload)
        if event.source != SOURCE_LOGIC_LLM:
            return False

        channel = event.channel or "unknown"
        session_id = resolve_session_id(self._config, channel=channel)
        message_id = event.correlation_id or event.reply_to_message_id or "qa-unknown"
        text = f"[Bot Q&A] {event.content.strip()}"
        self._store.append_chat(
            session_id=session_id,
            channel=channel,
            timestamp=_now_iso(),
            text=text,
            author="bot",
            message_id=message_id,
        )
        set_active_session_for_channel(self._store, channel=channel, session_id=session_id)
        print(
            f"[sub-qa-memory-batch] queued chat record session={session_id} "
            f"correlation={(event.correlation_id or '')[:8]}",
            file=sys.stderr,
            flush=True,
        )
        return True

    def __init__(self, store: StreamTextStore, config: RecordConfig) -> None:
        self._store = store
        self._config = config


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
