import os

from bus.topology import DEFAULT_EXCHANGE


def rabbitmq_url() -> str:
    return os.environ.get("RABBITMQ_URL", "amqp://guest:guest@127.0.0.1:5672/")


def stream_exchange() -> str:
    return os.environ.get("STREAM_EXCHANGE", DEFAULT_EXCHANGE)
