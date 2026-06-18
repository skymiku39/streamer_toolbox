from __future__ import annotations

from events import ChatMessageEvent

from sub_tts.filter import TtsMessageFilter, TtsMessageFilterConfig
from sub_tts.queue_worker import TtsPlaybackQueue
from sub_tts.subscriber import ChatTtsSubscriber
from tts.noop import NoOpTtsEngine


def _payload(content: str) -> dict:
    return ChatMessageEvent(
        schema_version=1,
        topic="chat.message",
        platform="twitch",
        message_id="msg-1",
        author_name="alice",
        content=content,
        timestamp="2026-01-01T00:00:00Z",
        channel="ch",
    ).to_dict()


def test_subscriber_skips_commands_and_enqueues_speech() -> None:
    engine = NoOpTtsEngine(record=True)
    playback = TtsPlaybackQueue(engine, cooldown_seconds=0, max_queue_size=10)
    subscriber = ChatTtsSubscriber(
        message_filter=TtsMessageFilter(TtsMessageFilterConfig()),
        playback=playback,
    )

    subscriber.handle(_payload("!cmd"))
    subscriber.handle(_payload("你好"))
    playback.shutdown()

    received, spoken, skipped, _pending = subscriber.stats()
    assert received == 2
    assert skipped == 1
    assert spoken == 1
    assert engine.spoken == ("alice 說 你好",)
