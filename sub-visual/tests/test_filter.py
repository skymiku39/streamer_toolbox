from sub_visual.config import FilterConfig
from sub_visual.filter import MessageFilter


def test_accepts_normal_message() -> None:
    filt = MessageFilter(FilterConfig())
    result = filt.evaluate("你好世界")
    assert result.accepted


def test_blocks_commands_by_default() -> None:
    filt = MessageFilter(FilterConfig())
    result = filt.evaluate("!hello")
    assert not result.accepted
    assert result.reason == "command"


def test_blocks_short_messages() -> None:
    filt = MessageFilter(FilterConfig(min_length=5))
    result = filt.evaluate("hi")
    assert not result.accepted
    assert result.reason == "too_short"


def test_blocks_keywords_case_insensitive() -> None:
    filt = MessageFilter(FilterConfig(blocked_keywords=["spam"]))
    result = filt.evaluate("This is SPAM content")
    assert not result.accepted
    assert result.reason == "blocked_keyword:spam"


def test_blocks_urls_when_enabled() -> None:
    filt = MessageFilter(FilterConfig(block_urls=True))
    result = filt.evaluate("check https://example.com")
    assert not result.accepted
    assert result.reason == "url"
