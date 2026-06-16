from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from stream_store.session import normalize_channel

ALLOW = "allow"
CACHED = "cached"
CANNED = "canned"

DEFAULT_WINDOW_SECONDS = 120
DEFAULT_CANNED_REPLY = "這題剛剛回答過囉，換個問題試試～"
DEFAULT_HARD_CANNED_REPLY = "問太快了啦，等一下再問～"


@dataclass(frozen=True)
class FlowDecision:
    action: str
    reply: str = ""

    @property
    def should_call_llm(self) -> bool:
        return self.action == ALLOW


class AskFlowGuard:
    """同頻道、同問題在短時間內重複時，跳過主 LLM，改回快取答案或罐頭回覆。"""

    def __init__(
        self,
        *,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        canned_reply: str = DEFAULT_CANNED_REPLY,
        hard_canned_reply: str = DEFAULT_HARD_CANNED_REPLY,
        now: Callable[[], float] | None = None,
    ) -> None:
        self._window_seconds = max(1, window_seconds)
        self._canned_reply = canned_reply
        self._hard_canned_reply = hard_canned_reply
        self._now = now or time.time
        self._events: dict[str, list[float]] = {}
        self._last_reply: dict[str, str] = {}
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls) -> AskFlowGuard:
        window = int(
            os.environ.get("LLM_FLOW_DEDUP_WINDOW_SECONDS", str(DEFAULT_WINDOW_SECONDS))
        )
        canned = (
            os.environ.get("LLM_FLOW_DEDUP_CANNED_REPLY") or DEFAULT_CANNED_REPLY
        ).strip() or DEFAULT_CANNED_REPLY
        hard_canned = (
            os.environ.get("LLM_FLOW_DEDUP_HARD_CANNED_REPLY") or DEFAULT_HARD_CANNED_REPLY
        ).strip() or DEFAULT_HARD_CANNED_REPLY
        return cls(
            window_seconds=window,
            canned_reply=canned,
            hard_canned_reply=hard_canned,
        )

    @staticmethod
    def _key(channel: str, question: str) -> str:
        return f"{normalize_channel(channel)}:{question.strip().lower()}"

    def check(self, channel: str, question: str) -> FlowDecision:
        key = self._key(channel, question)
        now = self._now()
        cutoff = now - self._window_seconds
        with self._lock:
            recent = [ts for ts in self._events.get(key, []) if ts >= cutoff]
            prior = len(recent)
            recent.append(now)
            self._events[key] = recent
            if prior == 0:
                return FlowDecision(ALLOW)
            if prior == 1:
                cached = self._last_reply.get(key, "")
                if cached:
                    return FlowDecision(CACHED, cached)
                return FlowDecision(CANNED, self._canned_reply)
            return FlowDecision(CANNED, self._hard_canned_reply)

    def record_reply(self, channel: str, question: str, reply: str) -> None:
        key = self._key(channel, question)
        with self._lock:
            self._last_reply[key] = reply
