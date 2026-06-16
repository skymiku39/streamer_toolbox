from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

from aio_pika import Exchange
from events import ChatMessageEvent, EventSubEvent

from bus.rabbitmq import publish_topic

logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    async def publish_chat(self, event: ChatMessageEvent) -> None: ...

    async def publish_eventsub(self, event: EventSubEvent) -> None: ...


class MqEventPublisher:
    def __init__(
        self,
        exchange: Exchange,
        *,
        publish_chat: Callable[[dict], Awaitable[None]] | None = None,
    ) -> None:
        self._exchange = exchange
        self._publish_chat = publish_chat

    async def publish_chat(self, event: ChatMessageEvent) -> None:
        payload = event.to_dict()
        if self._publish_chat is not None:
            await self._publish_chat(payload)
        else:
            await publish_topic(self._exchange, event.topic, payload)
        logger.info(
            "published chat.message %s #%s %s",
            event.message_id[:8],
            event.channel,
            event.author_name,
        )

    async def publish_eventsub(self, event: EventSubEvent) -> None:
        await publish_topic(self._exchange, event.topic, event.to_dict())
        logger.info(
            "published %s user=%s broadcaster=%s",
            event.topic,
            event.user_name or event.user_id,
            event.broadcaster_id,
        )
