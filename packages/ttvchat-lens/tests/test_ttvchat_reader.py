from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ttvchat_lens.reader import ChatMessage, channel_url, parse_irc_line, parse_twitch_channel

_PRIVMSG = (
    "@badge-info=;badges=moderator/1;client-nonce=nonce;color=#FF0000;"
    "display-name=TestUser;emotes=;first-msg=0;flags=;id=abc-123;mod=1;"
    "room-id=12345;subscriber=1;tmi-sent-ts=1609459200000;turbo=0;"
    "user-id=999;user-type=mod "
    ":testuser!testuser@testuser.tmi.twitch.tv PRIVMSG #skymiku39 :Hello world"
)


class TestParseTwitchChannel:
    def test_bare_channel(self) -> None:
        assert parse_twitch_channel("Skymiku39") == "skymiku39"

    def test_hash_prefix(self) -> None:
        assert parse_twitch_channel("#skymiku39") == "skymiku39"

    def test_twitch_url(self) -> None:
        assert parse_twitch_channel("https://www.twitch.tv/skymiku39") == "skymiku39"

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="無法從輸入解析"):
            parse_twitch_channel("not a channel")


def test_channel_url() -> None:
    assert channel_url("Skymiku39") == "https://www.twitch.tv/skymiku39"


class TestParseIrcLine:
    def test_privmsg_with_tags(self) -> None:
        line = parse_irc_line(_PRIVMSG)
        assert line is not None
        assert line.command == "PRIVMSG"
        assert line.nick == "testuser"
        assert line.tags["display-name"] == "TestUser"
        assert line.tags["id"] == "abc-123"
        assert line.trailing == "Hello world"
        assert line.params == ["#skymiku39"]

    def test_empty_line_returns_none(self) -> None:
        assert parse_irc_line("") is None

    def test_unescape_tag_space(self) -> None:
        line = parse_irc_line("@display-name=test\\suser :nick!nick@host PRIVMSG #ch :hi")
        assert line is not None
        assert line.tags["display-name"] == "test user"


class TestChatMessageFromIrc:
    def test_maps_privmsg_fields(self) -> None:
        irc = parse_irc_line(_PRIVMSG)
        assert irc is not None
        msg = ChatMessage.from_irc("skymiku39", irc)
        assert msg.message_id == "abc-123"
        assert msg.author_name == "TestUser"
        assert msg.author_id == "999"
        assert msg.message == "Hello world"
        assert msg.timestamp == datetime(2021, 1, 1, 0, 0, tzinfo=UTC)
        assert msg.is_moderator is True
        assert msg.is_member is True
        assert msg.color == "#FF0000"

    def test_to_dict_round_trip_keys(self) -> None:
        irc = parse_irc_line(_PRIVMSG)
        assert irc is not None
        data = ChatMessage.from_irc("skymiku39", irc).to_dict()
        assert data["author_name"] == "TestUser"
        assert data["message"] == "Hello world"
        assert "timestamp" in data
