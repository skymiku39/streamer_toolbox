from unittest.mock import MagicMock

import discord

from ingress_discord.gateway import build_intents, parse_discord_message


def _make_message(
    *,
    content: str = "hello",
    author_bot: bool = False,
    with_reply: bool = False,
) -> discord.Message:
    message = MagicMock(spec=discord.Message)
    message.id = 1234567890123456789
    message.content = content
    message.type = discord.MessageType.default
    message.created_at = discord.utils.utcnow()
    message.attachments = []

    author = MagicMock()
    author.bot = author_bot
    author.id = 987654321098765432
    author.name = "discord_user"
    author.display_name = "Discord User"
    message.author = author

    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 111222333444555666
    channel.name = "general"
    message.channel = channel

    guild = MagicMock()
    guild.id = 777888999000111222
    guild.name = "My Server"
    message.guild = guild
    channel.guild = guild

    if with_reply:
        referenced = MagicMock(spec=discord.Message)
        referenced.id = 999888777666555444
        referenced.content = "original"
        referenced.author = MagicMock()
        referenced.author.display_name = "Original Author"
        referenced.author.name = "original_author"

        reference = MagicMock()
        reference.resolved = referenced
        message.reference = reference
    else:
        message.reference = None

    return message


def test_parse_discord_message_maps_fields() -> None:
    parsed = parse_discord_message(_make_message())
    assert parsed is not None
    assert parsed.message_id == "1234567890123456789"
    assert parsed.author_name == "Discord User"
    assert parsed.login == "discord_user"
    assert parsed.channel == "My Server/general"
    assert parsed.raw["source"] == "discord_gateway"
    assert parsed.raw["guild_id"] == "777888999000111222"


def test_parse_discord_message_skips_bots() -> None:
    assert parse_discord_message(_make_message(author_bot=True)) is None


def test_parse_discord_message_skips_empty() -> None:
    assert parse_discord_message(_make_message(content="   ")) is None


def test_parse_discord_message_includes_reply() -> None:
    parsed = parse_discord_message(_make_message(with_reply=True))
    assert parsed is not None
    assert parsed.reply is not None
    assert parsed.reply["message_id"] == "999888777666555444"
    assert parsed.reply["author_name"] == "Original Author"


def test_build_intents_enables_message_content() -> None:
    intents = build_intents()
    assert intents.message_content is True
    assert intents.guilds is True
