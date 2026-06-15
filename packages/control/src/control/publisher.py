from __future__ import annotations

import logging
import os
from typing import Any

import pika

from bus.config import rabbitmq_url, stream_exchange
from bus.rabbitmq import connect_blocking, publish_topic_blocking
from events import ConfigChangedEvent

logger = logging.getLogger(__name__)


def active_profile_id() -> str:
    return (os.environ.get("STREAMER_PROFILE_ID") or "default").strip() or "default"


def publish_config_changed_blocking(
    channel: pika.adapters.blocking_connection.BlockingChannel,
    *,
    exchange_name: str,
    module_id: str,
    config_file: str,
    profile_id: str | None = None,
) -> None:
    event = ConfigChangedEvent.build(
        module_id=module_id,
        config_file=config_file,
        profile_id=profile_id or active_profile_id(),
    )
    publish_topic_blocking(
        channel,
        exchange_name=exchange_name,
        routing_key=event.topic,
        payload=event.to_dict(),
    )


def try_publish_config_changed(
    *,
    module_id: str,
    config_file: str,
    profile_id: str | None = None,
) -> bool:
    url = rabbitmq_url()
    if not url:
        logger.warning("config.changed skipped: RABBITMQ_URL is not set")
        return False
    connection: Any = None
    try:
        connection = connect_blocking(url)
        channel = connection.channel()
        publish_config_changed_blocking(
            channel,
            exchange_name=stream_exchange(),
            module_id=module_id,
            config_file=config_file,
            profile_id=profile_id,
        )
        return True
    except Exception as exc:
        logger.warning("config.changed publish failed: %s", exc)
        return False
    finally:
        if connection is not None and connection.is_open:
            connection.close()
