from app.processes.base import PublisherSpec, SubscriberSpec
from app.processes.registry import registry
from pkg_bus.topology import (
    DEFAULT_EXCHANGE,
    QUEUE_BOT_LOGIC_INBOX,
    QUEUE_CHARACTER_BRAIN_CHAT_MESSAGE,
    QUEUE_CHARACTER_FACE_CHARACTER_TURN,
    QUEUE_CHARACTER_STAGE,
    QUEUE_CHARACTER_VOICE_TURN,
    QUEUE_IO_LOG_CHAT_MESSAGE,
    QUEUE_SUB_LLM,
    QUEUE_SHOW_OVERLAY_CHAT_MESSAGE,
    QUEUE_STREAM_RECORD_CHAT_MESSAGE,
    QUEUE_TTS_CHAT_MESSAGE,
    QUEUE_TWITCH_CONNECTOR_CHAT_REPLY,
    QUEUE_VISUAL_CHAT_MESSAGE,
)


def register_builtin_processes() -> None:
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
            name="ingress-twitch-eventsub",
            module="ingress_twitch_eventsub",
            description="Twitch EventSub → RabbitMQ chat.message / eventsub.*",
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
    registry.register_publisher(
        PublisherSpec(
            name="ingress-twitch-audio",
            module="ingress_twitch_audio",
            description="Twitch live audio STT → RabbitMQ stt.segment",
            kind="publisher",
            exchange=DEFAULT_EXCHANGE,
        )
    )
    registry.register_publisher(
        PublisherSpec(
            name="ingress-yt-read",
            module="ingress_yt_read",
            description="tubechat_lens YouTube → RabbitMQ chat.message",
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
            name="sub-stream-record",
            module="sub_stream_record",
            description="chat.message → SQLite 記錄層（Phase 1 聊天室）",
            kind="subscriber",
            exchange=DEFAULT_EXCHANGE,
            queue=QUEUE_STREAM_RECORD_CHAT_MESSAGE,
        )
    )
    registry.register_subscriber(
        SubscriberSpec(
            name="sub-tts",
            module="sub_tts",
            description="chat.message → 觀眾彈幕 TTS 朗讀",
            kind="subscriber",
            exchange=DEFAULT_EXCHANGE,
            queue=QUEUE_TTS_CHAT_MESSAGE,
        )
    )
    registry.register_subscriber(
        SubscriberSpec(
            name="sub-character-stage",
            module="sub_character_stage",
            description="character audio + expression → OBS stage sync",
            kind="subscriber",
            exchange=DEFAULT_EXCHANGE,
            queue=QUEUE_CHARACTER_STAGE,
        )
    )
    registry.register_subscriber(
        SubscriberSpec(
            name="sub-visual",
            module="sub_visual",
            description="chat.message → subtitle file / Spout2",
            kind="subscriber",
            exchange=DEFAULT_EXCHANGE,
            queue=QUEUE_VISUAL_CHAT_MESSAGE,
        )
    )
    registry.register_subscriber(
        SubscriberSpec(
            name="sub-bot-logic",
            module="sub_bot_logic",
            description="chat.message + eventsub.* → chat.reply",
            kind="subscriber",
            exchange=DEFAULT_EXCHANGE,
            queue=QUEUE_BOT_LOGIC_INBOX,
        )
    )
    registry.register_subscriber(
        SubscriberSpec(
            name="sub-show-overlay",
            module="sub_show_overlay",
            description="chat.message → overlay HTTP + IPC",
            kind="subscriber",
            exchange=DEFAULT_EXCHANGE,
            queue=QUEUE_SHOW_OVERLAY_CHAT_MESSAGE,
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
    registry.register_subscriber(
        SubscriberSpec(
            name="sub-llm",
            module="sub_llm",
            description="chat.message + stt.segment → chat.reply (logic-llm)",
            kind="subscriber",
            exchange=DEFAULT_EXCHANGE,
            queue=QUEUE_SUB_LLM,
        )
    )
    registry.register_subscriber(
        SubscriberSpec(
            name="sub-character-face",
            module="sub_character_face",
            description="character.turn → character.expression.ready",
            kind="subscriber",
            exchange=DEFAULT_EXCHANGE,
            queue=QUEUE_CHARACTER_FACE_CHARACTER_TURN,
        )
    )
    registry.register_subscriber(
        SubscriberSpec(
            name="sub-character-voice",
            module="sub_character_voice",
            description="character.turn → TTS 合成 → character.audio.ready",
            kind="subscriber",
            exchange=DEFAULT_EXCHANGE,
            queue=QUEUE_CHARACTER_VOICE_TURN,
        )
    )
    registry.register_subscriber(
        SubscriberSpec(
            name="twitch-connector",
            module="twitch_connector",
            description="chat.reply → Twitch Helix 發話（Egress）",
            kind="subscriber",
            exchange=DEFAULT_EXCHANGE,
            queue=QUEUE_TWITCH_CONNECTOR_CHAT_REPLY,
        )
    )
