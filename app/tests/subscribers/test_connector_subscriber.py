from unittest.mock import MagicMock

import pytest

from events import TOPIC_CHAT_REPLY, ChatReplyEvent
from twitch_connector.dispatcher import ChatReplyDispatcher, UnsupportedPlatformError
from twitch_connector.subscriber import ReplySubscriber
from twitch_connector.twitch_sender import TwitchSendError


class FlakySender:
    def __init__(self, fail_times: int = 0) -> None:
        self.fail_times = fail_times
        self.attempts = 0
        self.calls: list[str] = []

    def send(
        self,
        channel: str,
        content: str,
        *,
        reply_to_message_id: str | None = None,
    ) -> None:
        self.attempts += 1
        if self.fail_times > 0:
            self.fail_times -= 1
            raise TwitchSendError("temporary failure")
        self.calls.append(content)


def _payload(**overrides) -> dict:
    base = {
        "schema_version": 1,
        "topic": TOPIC_CHAT_REPLY,
        "platform": "twitch",
        "channel": "test_channel",
        "content": "pong",
        "source": "logic-commands",
        "sender": "bot",
    }
    base.update(overrides)
    return base


def test_successful_send() -> None:
    sender = FlakySender()
    subscriber = ReplySubscriber(ChatReplyDispatcher(senders={"twitch": sender}))
    subscriber.handle(_payload())
    assert sender.calls == ["pong"]


def test_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("twitch_connector.subscriber.time.sleep", lambda _: None)
    sender = FlakySender(fail_times=2)
    subscriber = ReplySubscriber(
        ChatReplyDispatcher(senders={"twitch": sender}),
        max_retries=3,
    )
    subscriber.handle(_payload())
    assert sender.attempts == 3
    assert sender.calls == ["pong"]


def test_publishes_system_error_after_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("twitch_connector.subscriber.time.sleep", lambda _: None)
    sender = FlakySender(fail_times=5)
    publish_error = MagicMock()
    subscriber = ReplySubscriber(
        ChatReplyDispatcher(senders={"twitch": sender}),
        publish_error=publish_error,
        max_retries=2,
    )
    subscriber.handle(_payload())
    publish_error.assert_called_once()
    payload = publish_error.call_args.args[0]
    assert payload["topic"] == "system.error"
    assert payload["component"] == "twitch-connector"


def test_invalid_payload_reports_error() -> None:
    publish_error = MagicMock()
    subscriber = ReplySubscriber(
        ChatReplyDispatcher(senders={"twitch": FlakySender()}),
        publish_error=publish_error,
    )
    subscriber.handle({"topic": TOPIC_CHAT_REPLY})
    publish_error.assert_called_once()


def test_unsupported_platform_reports_error() -> None:
    publish_error = MagicMock()

    class RaisingDispatcher:
        def dispatch(self, event: ChatReplyEvent) -> None:
            raise UnsupportedPlatformError("unsupported platform: youtube")

    subscriber = ReplySubscriber(RaisingDispatcher(), publish_error=publish_error)
    subscriber.handle(_payload(platform="youtube"))
    publish_error.assert_called_once()
