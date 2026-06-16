from events import TOPIC_CHAT_MESSAGE, ChatMessageEvent

from ingress_discord.mapping import DiscordChatMessage, build_chat_event, parse_reply


def _sample_discord_message() -> DiscordChatMessage:
    return DiscordChatMessage(
        message_id="1234567890123456789",
        author_id="987654321098765432",
        author_name="Discord 使用者",
        login="discord_user",
        content="你好世界",
        timestamp="2026-06-12T17:00:00+00:00",
        channel="My Server/general",
        channel_id="111222333444555666",
        guild_id="777888999000111222",
        reply={
            "message_id": "999888777666555444",
            "author_name": "原訊息作者",
            "content": "被回覆的內容",
        },
        raw={
            "source": "discord_gateway",
            "guild_id": "777888999000111222",
            "channel_id": "111222333444555666",
            "message_type": "MessageType.default",
        },
    )


def test_build_chat_event_platform_discord() -> None:
    event = build_chat_event(_sample_discord_message())
    assert event.platform == "discord"
    assert event.topic == TOPIC_CHAT_MESSAGE
    assert event.author_name == "Discord 使用者"
    assert event.login == "discord_user"
    assert event.channel == "My Server/general"
    assert event.reply is not None
    assert event.reply["message_id"] == "999888777666555444"


def test_build_chat_event_round_trip() -> None:
    event = build_chat_event(_sample_discord_message())
    restored = ChatMessageEvent.from_json(event.to_json())
    assert restored == event


def test_parse_reply_requires_message_id_and_author() -> None:
    assert parse_reply(None) is None
    assert parse_reply({}) is None
    assert parse_reply({"message_id": "1"}) is None
    assert parse_reply({"author_name": "x"}) is None


def test_parse_reply_normalizes_fields() -> None:
    reply = parse_reply(
        {
            "message_id": 123,
            "author_name": "作者",
            "content": "內容",
        }
    )
    assert reply == {
        "message_id": "123",
        "author_name": "作者",
        "content": "內容",
    }
