from datetime import datetime, timedelta, timezone

from events import TOPIC_CHAT_MESSAGE, TOPIC_STT_SEGMENT, ChatMessageEvent, SttSegmentEvent

from sub_llm.context_buffer import ChatContextBuffer, LiveContextBuffer, SttContextBuffer


def _segment(text: str, *, channel: str, offset_minutes: int = 0) -> SttSegmentEvent:
    timestamp = (datetime.now(timezone.utc) - timedelta(minutes=offset_minutes)).isoformat()
    return SttSegmentEvent(
        schema_version=1,
        topic=TOPIC_STT_SEGMENT,
        platform="twitch",
        channel=channel,
        segment_id=f"seg-{channel}-{text}",
        text=text,
        timestamp=timestamp,
        start_sec=10.0,
    )


def _chat(
    content: str,
    *,
    channel: str = "room_a",
    author_name: str = "viewer",
    author_id: str = "viewer-id",
) -> ChatMessageEvent:
    return ChatMessageEvent(
        schema_version=1,
        topic=TOPIC_CHAT_MESSAGE,
        platform="twitch",
        message_id=f"msg-{content[:8]}",
        author_name=author_name,
        author_id=author_id,
        content=content,
        timestamp=datetime.now(timezone.utc).isoformat(),
        channel=channel,
    )


def test_context_text_includes_recent_segments_for_channel() -> None:
    buffer = SttContextBuffer(window_minutes=5)
    buffer.add_segment(_segment("第一段", channel="room_a"))
    buffer.add_segment(_segment("第二段", channel="room_a"))
    context = buffer.context_text("room_a")
    assert "第一段" in context
    assert "第二段" in context


def test_context_text_prunes_old_segments() -> None:
    buffer = SttContextBuffer(window_minutes=1)
    buffer.add_segment(_segment("舊片段", channel="demo", offset_minutes=10))
    buffer.add_segment(_segment("新片段", channel="demo", offset_minutes=0))
    context = buffer.context_text("demo")
    assert "舊片段" not in context
    assert "新片段" in context


def test_context_text_isolated_by_channel() -> None:
    buffer = SttContextBuffer(window_minutes=5)
    buffer.add_segment(_segment("A 房間語音", channel="room_a"))
    buffer.add_segment(_segment("B 房間語音", channel="room_b"))
    context_a = buffer.context_text("room_a")
    context_b = buffer.context_text("room_b")
    assert "A 房間語音" in context_a
    assert "B 房間語音" not in context_a
    assert "B 房間語音" in context_b
    assert "A 房間語音" not in context_b


def test_chat_context_buffer_includes_recent_messages() -> None:
    buffer = ChatContextBuffer(window_minutes=5)
    buffer.add_message(_chat("你好", channel="room_a"))
    buffer.add_message(_chat("再見", channel="room_a"))
    context = buffer.context_text("room_a")
    assert "viewer: 你好" in context
    assert "viewer: 再見" in context


def test_chat_context_buffer_skips_bot_author_id() -> None:
    buffer = ChatContextBuffer(window_minutes=5, skip_author_ids=frozenset({"bot-id"}))
    buffer.add_message(_chat("bot 回覆", author_id="bot-id"))
    buffer.add_message(_chat("觀眾發言", author_id="viewer-id"))
    context = buffer.context_text("room_a")
    assert "bot 回覆" not in context
    assert "觀眾發言" in context


def test_live_context_buffer_merges_stt_and_chat() -> None:
    buffer = LiveContextBuffer(window_minutes=5, skip_author_ids=frozenset({"bot-id"}))
    buffer.add_segment(_segment("主播說話", channel="room_a"))
    buffer.add_chat_message(_chat("觀眾聊天", channel="room_a", author_id="viewer-id"))
    context = buffer.context_text("room_a")
    stt_count, chat_count, context_len, has_stream = buffer.stats("room_a")
    assert "主播說話" in context
    assert "觀眾聊天" in context
    assert stt_count == 1
    assert chat_count == 1
    assert context_len > 0
    assert has_stream is False


def test_live_context_buffer_includes_stream_metadata() -> None:
    from events import TOPIC_STREAM_METADATA, StreamMetadataEvent

    buffer = LiveContextBuffer(window_minutes=5)
    buffer.update_stream_metadata(
        StreamMetadataEvent(
            schema_version=1,
            topic=TOPIC_STREAM_METADATA,
            platform="twitch",
            channel="room_a",
            timestamp="2026-06-13T10:00:00+00:00",
            snapshot_id="snap-1",
            is_live=True,
            title="打 Boss",
            game_name="Dark Souls",
            display_name="Streamer",
            started_at="2026-06-13T09:00:00+00:00",
            duration_seconds=3600,
            viewer_count=50,
            stream_url="https://www.twitch.tv/room_a",
        )
    )
    context = buffer.context_text("room_a")
    _, _, _, has_stream = buffer.stats("room_a")
    assert has_stream is True
    assert "【直播狀態" in context
    assert "打 Boss" in context
    assert "Dark Souls" in context
    assert "1h 0m" in context
