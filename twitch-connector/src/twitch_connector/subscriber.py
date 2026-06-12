"""chat.reply 訂閱處理：節流、重試、system.error 上報。"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pkg_events import (
    TOPIC_SYSTEM_ERROR,
    ChatReplyEvent,
    SystemErrorEvent,
)

from twitch_connector.dispatcher import ChatReplyDispatcher, UnsupportedPlatformError
from twitch_connector.twitch_sender import TwitchSendError

PROCESS_NAME = "twitch-connector"
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
    ) -> None:
        self._dispatcher = dispatcher
        self._publish_error = publish_error
        self._max_retries = max_retries
        self._retry_base_seconds = retry_base_seconds

    def handle(self, payload: dict) -> None:
        try:
            event = ChatReplyEvent.from_dict(payload)
        except (ValueError, KeyError, TypeError) as exc:
            self._report_error("invalid chat.reply payload", detail={"error": str(exc)})
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
