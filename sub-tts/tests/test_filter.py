from __future__ import annotations

from pkg_events import ChatMessageEvent

from sub_tts.filter import MessageFilter, MessageFilterConfig


def _event(content: str, *, author: str = "viewer1") -> ChatMessageEvent:
    return ChatMessageEvent(
        schema_version=1,
        topic="chat.message",
        platform="twitch",
        message_id="msg-1",
        author_name=author,
        content=content,
        timestamp="2026-01-01T00:00:00Z",
        channel="testchannel",
    )


def test_skip_command_messages() -> None:
    filt = MessageFilter(MessageFilterConfig(skip_commands=True))
    assert filt.should_speak(_event("!hello")) is False
    assert filt.should_speak(_event("一般訊息")) is True


def test_skip_urls() -> None:
    filt = MessageFilter(MessageFilterConfig(skip_urls=True))
    assert filt.should_speak(_event("看這個 https://example.com")) is False
    assert filt.should_speak(_event("沒有連結")) is True


def test_blacklist_and_max_length() -> None:
    filt = MessageFilter(
        MessageFilterConfig(
            blacklist=frozenset({"spam"}),
            max_length=10,
        )
    )
    assert filt.should_speak(_event("這是 spam 訊息")) is False
    assert filt.should_speak(_event("12345678901")) is False
    assert filt.should_speak(_event("ok")) is True


def test_format_text_uses_template() -> None:
    filt = MessageFilter(MessageFilterConfig(template="{author_name}:{content}"))
    assert filt.format_text(_event("嗨")) == "viewer1:嗨"
