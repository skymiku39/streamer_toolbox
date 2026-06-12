from app.processes.base import PublisherSpec, SubscriberSpec
from app.processes.registry import registry
from pkg_bus.topology import DEFAULT_EXCHANGE, QUEUE_IO_LOG_CHAT_MESSAGE


def register_builtin_processes() -> None:
    registry.register_publisher(
        PublisherSpec(
            name="ingress-twitch-chat",
            module="ingress_twitch_chat",
            description="Twitch IRC → RabbitMQ chat.message",
            kind="publisher",
            exchange=DEFAULT_EXCHANGE,
        )
    )
    registry.register_subscriber(
        SubscriberSpec(
            name="sub-io-log",
            module="sub_io_log",
            description="chat.message → console + JSONL",
            kind="subscriber",
            exchange=DEFAULT_EXCHANGE,
            queue=QUEUE_IO_LOG_CHAT_MESSAGE,
        )
    )
