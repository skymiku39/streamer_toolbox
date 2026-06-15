from events import StreamMetadataEvent

from sub_live_status.status_messages import build_live_status_message


def _metadata_event(**overrides) -> StreamMetadataEvent:
    base = {
        "schema_version": 1,
        "topic": "stream.metadata",
        "platform": "twitch",
        "channel": "skymiku39",
        "timestamp": "2026-06-14T08:00:00+00:00",
        "snapshot_id": "snap-1",
        "is_live": True,
        "title": "【工作】繼續製作直播小工具",
        "game_name": "Just Chatting",
        "duration_seconds": 3480,
    }
    base.update(overrides)
    return StreamMetadataEvent.from_dict(base)


def test_build_live_status_message_includes_title_and_game() -> None:
    message = build_live_status_message(_metadata_event())
    assert "【工作】繼續製作直播小工具" in message
    assert "Just Chatting" in message
    assert "問答模式未啟用" in message
    assert "直播中" in message


def test_build_live_status_message_offline() -> None:
    message = build_live_status_message(_metadata_event(is_live=False, duration_seconds=None))
    assert "離線" in message
