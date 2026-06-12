from __future__ import annotations

import logging
from typing import Protocol

from aio_pika import Exchange

from pkg_bus.rabbitmq import publish_topic
from pkg_events import ChatMessageEvent, EventSubEvent

logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    async def publish_chat(self, event: ChatMessageEvent) -> None: ...

    async def publish_eventsub(self, event: EventSubEvent) -> None: ...


class MqEventPublisher:
    def __init__(self, exchange: Exchange) -> None:
        self._exchange = exchange

    async def publish_chat(self, event: ChatMessageEvent) -> None:
        await publish_topic(self._exchange, event.topic, event.to_dict())
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
