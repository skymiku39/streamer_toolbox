from ingress_twitch_eventsub.first_chat import FirstChatTracker


def test_first_chat_claim_once_per_stream_session() -> None:
    tracker = FirstChatTracker()
    tracker.arm_session(channel_name="channel_name", stream_id="stream-1")

    first = tracker.try_claim(
        channel_name="channel_name",
        login="viewer",
        display_name="Viewer",
        broadcaster_id="broadcaster-1",
        is_broadcaster=False,
        is_shared_chat=False,
    )
    second = tracker.try_claim(
        channel_name="channel_name",
        login="viewer2",
        display_name="Viewer2",
        broadcaster_id="broadcaster-1",
        is_broadcaster=False,
        is_shared_chat=False,
    )

    assert first is not None
    assert first["stream_id"] == "stream-1"
    assert second is None


def test_first_chat_skips_broadcaster_and_shared_chat() -> None:
    tracker = FirstChatTracker()
    tracker.arm_session(channel_name="channel_name")

    assert (
        tracker.try_claim(
            channel_name="channel_name",
            login="host",
            display_name="Host",
            broadcaster_id="broadcaster-1",
            is_broadcaster=True,
            is_shared_chat=False,
        )
        is None
    )
    assert (
        tracker.try_claim(
            channel_name="channel_name",
            login="viewer",
            display_name="Viewer",
            broadcaster_id="broadcaster-1",
            is_broadcaster=False,
            is_shared_chat=True,
        )
        is None
    )
