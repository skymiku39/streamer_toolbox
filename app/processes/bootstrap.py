from app.processes.base import PublisherSpec, SubscriberSpec
from app.processes.registry import registry
from pkg_bus.topology import (
    DEFAULT_EXCHANGE,
    QUEUE_CHARACTER_BRAIN_CHAT_MESSAGE,
    QUEUE_IO_LOG_CHAT_MESSAGE,
)


def register_builtin_processes() -> None:
    registry.register_publisher(
        PublisherSpec(
            name="ingress-twitch-chat",
            module="ingress_twitch_chat",
            description="Twitch IRC → RabbitMQ chat.message (Phase 01 過渡)",
            kind="publisher",
            exchange=DEFAULT_EXCHANGE,
        )
    )
    registry.register_publisher(
        PublisherSpec(
            name="ingress-ttv-read",
            module="ingress_ttv_read",
            description="ttvchat_lens IRC → RabbitMQ chat.message",
            kind="publisher",
            exchange=DEFAULT_EXCHANGE,
        )
    )
    registry.register_publisher(
        PublisherSpec(
            name="ingress-discord",
            module="ingress_discord",
            description="Discord Gateway → RabbitMQ chat.message",
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
    registry.register_subscriber(
        SubscriberSpec(
            name="sub-character-brain",
            module="sub_character_brain",
            description="chat.message → character.turn (+ optional chat.reply)",
            kind="subscriber",
            exchange=DEFAULT_EXCHANGE,
            queue=QUEUE_CHARACTER_BRAIN_CHAT_MESSAGE,
        )
    )
