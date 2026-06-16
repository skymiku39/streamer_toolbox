"""chat.reply 訂閱處理：節流、重試、system.error 上報。"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from events import (
    TOPIC_SYSTEM_ERROR,
    ChatReplyEvent,
    SystemErrorEvent,
)

from stream_store.idempotency import IdempotencyStore
from twitch_connector.dispatcher import ChatReplyDispatcher, UnsupportedPlatformError
from twitch_connector.twitch_sender import TwitchSendError

PROCESS_NAME = "twitch-connector"
NAMESPACE_CHAT_REPLY = "twitch_connector.chat.reply"
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_SECONDS = 0.5


class ReplySubscriber:
    def __init__(
        self,
        dispatcher: ChatReplyDispatcher,
        *,
        publish_error: Callable[[dict[str, Any]], None] | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_base_seconds: float = DEFAULT_RETRY_BASE_SECONDS,
        idempotency: IdempotencyStore | None = None,
    ) -> None:
        self._dispatcher = dispatcher
        self._publish_error = publish_error
        self._max_retries = max_retries
        self._retry_base_seconds = retry_base_seconds
        self._idempotency = idempotency

    def handle(self, payload: dict) -> None:
        try:
            event = ChatReplyEvent.from_dict(payload)
        except (ValueError, KeyError, TypeError) as exc:
            self._report_error("invalid chat.reply payload", detail={"error": str(exc)})
            return

        dedup_key = self._dedup_key(event)
        claim_ok = True
        if self._idempotency is not None and dedup_key:
            claim_ok = self._idempotency.claim(NAMESPACE_CHAT_REPLY, dedup_key)
        if self._idempotency is not None and dedup_key and not claim_ok:
            print(
                f"skip duplicate chat.reply key={dedup_key[:24]}",
                file=sys.stderr,
                flush=True,
            )
            return

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                self._dispatcher.dispatch(event)
                print(
                    f"sent #{event.channel} ({event.source}): {event.content[:80]}",
                    flush=True,
                )
                return
            except UnsupportedPlatformError as exc:
                self._report_error(
                    str(exc),
                    detail={
                        "platform": event.platform,
                        "channel": event.channel,
                        "correlation_id": event.correlation_id,
                    },
                )
                return
            except (TwitchSendError, OSError) as exc:
                last_error = exc
                if attempt < self._max_retries:
                    delay = self._retry_base_seconds * (2 ** (attempt - 1))
                    print(
                        f"send failed (attempt {attempt}/{self._max_retries}), "
                        f"retry in {delay:.1f}s: {exc}",
                        file=sys.stderr,
                        flush=True,
                    )
                    time.sleep(delay)

        if last_error is not None:
            self._report_error(
                f"send failed after {self._max_retries} attempts: {last_error}",
                detail={
                    "channel": event.channel,
                    "source": event.source,
                    "correlation_id": event.correlation_id,
                },
            )

    @staticmethod
    def _dedup_key(event: ChatReplyEvent) -> str:
        correlation = (event.correlation_id or event.reply_to_message_id or "").strip()
        if not correlation:
            return ""
        return f"{event.source}:{correlation}"

    def _report_error(self, message: str, *, detail: dict[str, Any]) -> None:
        print(f"[error] {message}", file=sys.stderr, flush=True)
        if self._publish_error is None:
            return
        event = SystemErrorEvent(
            schema_version=1,
            topic=TOPIC_SYSTEM_ERROR,
            component=PROCESS_NAME,
            message=message,
            timestamp=datetime.now(UTC).isoformat(),
            detail=detail,
        )
        self._publish_error(event.to_dict())
