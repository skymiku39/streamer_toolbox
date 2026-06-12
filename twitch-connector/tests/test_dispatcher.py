from pkg_events import TOPIC_CHAT_REPLY, ChatReplyEvent

from twitch_connector.dispatcher import ChatReplyDispatcher, UnsupportedPlatformError


class RecordingSender:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    def send(
        self,
        channel: str,
        content: str,
        *,
        reply_to_message_id: str | None = None,
    ) -> None:
        self.calls.append((channel, content, reply_to_message_id))


def _reply_event(**overrides) -> ChatReplyEvent:
    payload = {
        "schema_version": 1,
        "topic": TOPIC_CHAT_REPLY,
        "platform": "twitch",
        "channel": "test_channel",
        "content": "hello",
        "source": "logic-commands",
        "sender": "bot",
        "reply_to_message_id": "msg-1",
        "correlation_id": "corr-1",
    }
    payload.update(overrides)
    return ChatReplyEvent.from_dict(payload)


def test_dispatch_twitch_sender() -> None:
    sender = RecordingSender()
    dispatcher = ChatReplyDispatcher(senders={"twitch": sender})
    event = _reply_event()
    dispatcher.dispatch(event)
    assert sender.calls == [("test_channel", "hello", "msg-1")]


def test_unsupported_platform_raises() -> None:
    dispatcher = ChatReplyDispatcher(senders={"twitch": RecordingSender()})
    event = _reply_event(platform="youtube")
    try:
        dispatcher.dispatch(event)
        raise AssertionError("expected UnsupportedPlatformError")
    except UnsupportedPlatformError as exc:
        assert "youtube" in str(exc)
