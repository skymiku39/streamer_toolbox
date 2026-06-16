from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tubechat_lens.reader import (
    ChatMessage,
    _extract_channel_handle,
    normalize_video_id,
    normalize_video_url,
)


class TestExtractChannelHandle:
    def test_handle_url(self) -> None:
        assert _extract_channel_handle("https://www.youtube.com/@skymiku39") == "skymiku39"

    def test_bare_handle_name(self) -> None:
        assert _extract_channel_handle("skymiku39") == "skymiku39"

    def test_watch_url_returns_none(self) -> None:
        assert _extract_channel_handle("https://www.youtube.com/watch?v=abcdefghijk") is None


class TestNormalizeVideoId:
    def test_direct_video_id(self) -> None:
        assert normalize_video_id("WJddL7w8Ycs") == "WJddL7w8Ycs"

    def test_watch_url(self) -> None:
        assert (
            normalize_video_id("https://www.youtube.com/watch?v=WJddL7w8Ycs")
            == "WJddL7w8Ycs"
        )

    @patch("tubechat_lens.reader._fetch_live_video_id_from_handle", return_value="WJddL7w8Ycs")
    def test_channel_handle_resolves_live(self, mock_fetch) -> None:
        assert normalize_video_id("skymiku39") == "WJddL7w8Ycs"
        mock_fetch.assert_called_once_with("skymiku39")

    def test_invalid_input_raises(self) -> None:
        with pytest.raises(ValueError, match="無法從輸入解析"):
            normalize_video_id("not a youtube thing")


def test_normalize_video_url() -> None:
    assert (
        normalize_video_url("WJddL7w8Ycs")
        == "https://www.youtube.com/watch?v=WJddL7w8Ycs"
    )


class TestChatMessageFromPytchat:
    def test_maps_pytchat_object(self) -> None:
        author = SimpleNamespace(
            name="Viewer",
            channelId="UC123",
            isChatSponsor=False,
            isChatModerator=True,
            isChatOwner=False,
            isVerified=False,
        )
        chat_obj = SimpleNamespace(
            id="yt-msg-1",
            author=author,
            message="hello yt",
            timestamp=1609459200000,
            type="textMessage",
            amountString="",
            currency="",
            json=lambda: {"id": "yt-msg-1"},
        )
        msg = ChatMessage.from_pytchat(chat_obj)
        assert msg.message_id == "yt-msg-1"
        assert msg.author_name == "Viewer"
        assert msg.author_id == "UC123"
        assert msg.message == "hello yt"
        assert msg.timestamp == datetime(2021, 1, 1, 0, 0, tzinfo=UTC)
        assert msg.is_moderator is True

    def test_to_dict_includes_core_fields(self) -> None:
        author = SimpleNamespace(
            name="Viewer",
            channelId="UC123",
            isChatSponsor=False,
            isChatModerator=False,
            isChatOwner=False,
            isVerified=False,
        )
        chat_obj = SimpleNamespace(
            id="yt-msg-2",
            author=author,
            message="hi",
            timestamp=0,
            type="textMessage",
            amountString="",
            currency="",
            json=lambda: {},
        )
        data = ChatMessage.from_pytchat(chat_obj).to_dict()
        assert data["message"] == "hi"
        assert data["author_name"] == "Viewer"
