from __future__ import annotations

from unittest.mock import patch

import pytest

from tubechat_lens.reader import _extract_channel_handle, normalize_video_id

_LIVE_HTML = (
    '<meta property="og:url" content="https://www.youtube.com/watch?v=WJddL7w8Ycs">'
)


class TestExtractChannelHandle:
    def test_handle_url(self) -> None:
        assert _extract_channel_handle("https://www.youtube.com/@skymiku39") == "skymiku39"

    def test_handle_live_url(self) -> None:
        assert _extract_channel_handle("https://www.youtube.com/@skymiku39/live") == "skymiku39"

    def test_bare_handle_name(self) -> None:
        assert _extract_channel_handle("skymiku39") == "skymiku39"

    def test_at_prefix(self) -> None:
        assert _extract_channel_handle("@skymiku39") == "skymiku39"

    def test_watch_url_returns_none(self) -> None:
        assert _extract_channel_handle("https://www.youtube.com/watch?v=abcdefghijk") is None

    def test_video_id_returns_none(self) -> None:
        assert _extract_channel_handle("abcdefghijk") is None


class TestNormalizeVideoId:
    def test_direct_video_id(self) -> None:
        assert normalize_video_id("WJddL7w8Ycs") == "WJddL7w8Ycs"

    def test_watch_url(self) -> None:
        assert (
            normalize_video_id("https://www.youtube.com/watch?v=WJddL7w8Ycs")
            == "WJddL7w8Ycs"
        )

    @patch("tubechat_lens.reader._fetch_live_video_id_from_handle", return_value="WJddL7w8Ycs")
    def test_channel_handle_resolves_live(self, _mock_fetch) -> None:
        assert normalize_video_id("skymiku39") == "WJddL7w8Ycs"
        _mock_fetch.assert_called_once_with("skymiku39")

    @patch("tubechat_lens.reader._fetch_live_video_id_from_handle", return_value="WJddL7w8Ycs")
    def test_channel_url_resolves_live(self, _mock_fetch) -> None:
        assert (
            normalize_video_id("https://www.youtube.com/@skymiku39")
            == "WJddL7w8Ycs"
        )
        _mock_fetch.assert_called_once_with("skymiku39")

    def test_invalid_input_raises(self) -> None:
        with pytest.raises(ValueError, match="無法從輸入解析"):
            normalize_video_id("not a youtube thing")
