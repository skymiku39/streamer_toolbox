from __future__ import annotations

import sys
import uuid
from collections.abc import Callable
from typing import Any

from events import (
    SOURCE_LOGIC_STATUS,
    TOPIC_CHAT_REPLY,
    TOPIC_STREAM_METADATA,
    ChatReplyEvent,
    StreamMetadataEvent,
)
from stream_store.idempotency import IdempotencyStore

from sub_live_status.status_messages import (
    build_live_status_message,
    live_status_announcement_enabled,
    resolve_status_channel,
)

NAMESPACE_STARTUP = "sub_live_status.startup"


class LiveStatusSubscriber:
    def __init__(
        self,
        *,
        publish: Callable[[str, dict[str, Any]], None],
        idempotency: IdempotencyStore,
    ) -> None:
        self._publish = publish
        self._idempotency = idempotency
        self._announced = False

    def handle(self, payload: dict[str, Any]) -> None:
        try:
            event = StreamMetadataEvent.from_dict(payload)
        except (ValueError, KeyError, TypeError) as exc:
            print(
                f"[sub-live-status] invalid stream.metadata payload: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return

        if event.topic != TOPIC_STREAM_METADATA:
            return

        print(
            f"[sub-live-status] stream metadata "
            f"live={event.is_live} game={event.game_name!r} title={event.title!r}",
            file=sys.stderr,
            flush=True,
        )

        if self._announced:
            return
        self._try_publish_startup_status(event)

    def _try_publish_startup_status(self, event: StreamMetadataEvent) -> None:
        if not live_status_announcement_enabled():
            print(
                "[sub-live-status] status announcement disabled",
                file=sys.stderr,
                flush=True,
            )
            self._announced = True
            return

        channel = resolve_status_channel() or (event.channel or "").strip().lstrip("#")
        if not channel:
            print(
                "[sub-live-status] status announcement skipped: TWITCH_CHANNEL not set",
                file=sys.stderr,
                flush=True,
            )
            return

        if not self._idempotency.claim(NAMESPACE_STARTUP, channel.lower()):
            print(
                "[sub-live-status] status announcement skipped: duplicate instance",
                file=sys.stderr,
                flush=True,
            )
            self._announced = True
            return

        content = build_live_status_message(event)
        correlation_id = f"status-{uuid.uuid4().hex[:12]}"
        reply = ChatReplyEvent(
            schema_version=1,
            topic=TOPIC_CHAT_REPLY,
            platform=event.platform or "twitch",
            channel=channel,
            content=content,
            reply_to_message_id=None,
            sender="bot",
            source=SOURCE_LOGIC_STATUS,
            correlation_id=correlation_id,
        )
        self._publish(TOPIC_CHAT_REPLY, reply.to_dict())
        self._announced = True
        print(
            f"[sub-live-status] status announcement published channel={channel} "
            f"chars={len(content)}",
            file=sys.stderr,
            flush=True,
        )
