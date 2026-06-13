from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import aio_pika
import pika
from aio_pika import DeliveryMode, ExchangeType, Message

from bus.topology import DEFAULT_EXCHANGE


def connect_blocking(url: str) -> pika.BlockingConnection:
    return pika.BlockingConnection(pika.URLParameters(url))


async def connect_async(url: str) -> aio_pika.RobustConnection:
    return await aio_pika.connect_robust(url)


async def declare_topic_exchange(
    channel: aio_pika.Channel,
    exchange_name: str = DEFAULT_EXCHANGE,
) -> aio_pika.Exchange:
    return await channel.declare_exchange(exchange_name, ExchangeType.TOPIC, durable=True)


async def publish_topic(
    exchange: aio_pika.Exchange,
    routing_key: str,
    payload: dict[str, Any],
) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    await exchange.publish(
        Message(body=body, delivery_mode=DeliveryMode.PERSISTENT),
        routing_key=routing_key,
    )


def publish_topic_blocking(
    channel: pika.adapters.blocking_connection.BlockingChannel,
    *,
    exchange_name: str,
    routing_key: str,
    payload: dict[str, Any],
) -> None:
    channel.exchange_declare(exchange=exchange_name, exchange_type="topic", durable=True)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    channel.basic_publish(
        exchange=exchange_name,
        routing_key=routing_key,
        body=body,
        properties=pika.BasicProperties(delivery_mode=2),
    )


def setup_subscriber_queue(
    channel: pika.adapters.blocking_connection.BlockingChannel,
    *,
    exchange_name: str,
    queue_name: str,
    routing_key: str,
) -> None:
    setup_subscriber_queue_multi(
        channel,
        exchange_name=exchange_name,
        queue_name=queue_name,
        routing_keys=[routing_key],
    )


def setup_subscriber_queue_multi(
    channel: pika.adapters.blocking_connection.BlockingChannel,
    *,
    exchange_name: str,
    queue_name: str,
    routing_keys: list[str],
) -> None:
    if not routing_keys:
        raise ValueError("routing_keys must not be empty")
    channel.exchange_declare(exchange=exchange_name, exchange_type="topic", durable=True)
    channel.queue_declare(queue=queue_name, durable=True)
    for routing_key in routing_keys:
        channel.queue_bind(queue=queue_name, exchange=exchange_name, routing_key=routing_key)
    channel.basic_qos(prefetch_count=1)


def setup_subscriber_queue_bindings(
    channel: pika.adapters.blocking_connection.BlockingChannel,
    *,
    exchange_name: str,
    queue_name: str,
    routing_keys: list[str],
) -> None:
    channel.exchange_declare(exchange=exchange_name, exchange_type="topic", durable=True)
    channel.queue_declare(queue=queue_name, durable=True)
    for routing_key in routing_keys:
        channel.queue_bind(queue=queue_name, exchange=exchange_name, routing_key=routing_key)
    channel.basic_qos(prefetch_count=1)


def consume_messages(
    channel: pika.adapters.blocking_connection.BlockingChannel,
    queue_name: str,
    handler: Callable[[dict[str, Any]], None],
) -> None:
    def on_message(
        ch: pika.adapters.blocking_connection.BlockingChannel,
        method: pika.spec.Basic.Deliver,
        _properties: pika.spec.BasicProperties,
        body: bytes,
    ) -> None:
        try:
            payload = json.loads(body.decode("utf-8"))
            handler(payload)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            raise

    channel.basic_consume(queue=queue_name, on_message_callback=on_message, auto_ack=False)
    channel.start_consuming()
