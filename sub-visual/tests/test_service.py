from pathlib import Path

import pytest

from pkg_events import TOPIC_CHAT_MESSAGE, ChatMessageEvent

from sub_visual.config import FilterConfig, SubtitleConfig
from sub_visual.service import SubtitleService


def _event(content: str, author: str = "觀眾A") -> ChatMessageEvent:
    return ChatMessageEvent(
        schema_version=1,
        topic=TOPIC_CHAT_MESSAGE,
        platform="twitch",
        message_id="msg-001",
        author_name=author,
        content=content,
        timestamp="2026-06-12T17:00:00+08:00",
        channel="test_channel",
    )


def test_writes_subtitle_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "subtitle.txt"
    config = SubtitleConfig(
        output_file=str(output),
        format_template="{username}: {message}",
        max_chars=80,
    )
    service = SubtitleService(config)

    update = service.handle_chat_message(_event("大家好"))
    assert update is not None
    assert not update.filtered
    assert update.text == "觀眾A: 大家好"
    assert output.read_text(encoding="utf-8") == "觀眾A: 大家好"
    service.close()


def test_truncates_long_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "subtitle.txt"
    config = SubtitleConfig(output_file=str(output), max_chars=10)
    service = SubtitleService(config)

    update = service.handle_chat_message(_event("這是一段很長的彈幕內容"))
    assert update is not None
    assert update.text.endswith("...")
    assert len(update.text) == 13
    service.close()


def test_filtered_command_not_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "subtitle.txt"
    service = SubtitleService(SubtitleConfig(output_file=str(output)))

    update = service.handle_chat_message(_event("!help"))
    assert update is not None
    assert update.filtered
    assert update.filter_reason == "command"
    assert not output.exists()
    service.close()


def test_custom_filter_blocks_keyword(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "subtitle.txt"
    config = SubtitleConfig(
        output_file=str(output),
        filter=FilterConfig(blocked_keywords=["廣告"]),
    )
    service = SubtitleService(config)

    update = service.handle_chat_message(_event("這是廣告訊息"))
    assert update is not None
    assert update.filtered
    assert update.filter_reason == "blocked_keyword:廣告"
    service.close()
