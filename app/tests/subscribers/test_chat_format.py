from sub_llm.chat_format import (
    cap_reply_for_chat,
    count_reply_content_chars,
    plain_text_for_chat,
    truncate_reply_for_chat,
)


def test_strips_bold_and_italic() -> None:
    assert plain_text_for_chat("**重點**與*斜體*") == "重點與斜體"
    assert plain_text_for_chat("__粗體__與_斜體_") == "粗體與斜體"


def test_strips_headers_and_links() -> None:
    text = "## 標題\n請看[官方文件](https://example.com)"
    assert plain_text_for_chat(text) == "標題\n請看官方文件"


def test_strips_code_and_blockquote() -> None:
    text = "> 引用\n`code` 與\n```py\nprint('hi')\n```"
    assert plain_text_for_chat(text) == "引用\ncode 與\nprint('hi')"


def test_count_reply_content_chars_excludes_tags_and_punctuation() -> None:
    text = "@viewer 你好，這是測試！#topic"
    assert count_reply_content_chars(text) == 6  # 你好這是測試


def test_truncate_reply_for_chat_preserves_tags() -> None:
    text = "@alice " + ("測" * 60) + "。"
    capped = truncate_reply_for_chat(text, 50)
    assert capped.startswith("@alice ")
    assert count_reply_content_chars(capped) == 50


def test_truncate_reply_for_chat_prefers_sentence_boundary() -> None:
    text = "前半段沒提到。" + ("中間很長的補充" * 8) + "。結尾不應出現。"
    capped = truncate_reply_for_chat(text, 20)
    assert count_reply_content_chars(capped) <= 20
    assert "結尾不應出現" not in capped
    assert capped.endswith("。") or capped.endswith("充")


def test_cap_reply_for_chat() -> None:
    text = "短回覆。"
    assert cap_reply_for_chat(text, 50) == text
    long_text = "這" * 55 + "。"
    assert count_reply_content_chars(cap_reply_for_chat(long_text, 50)) == 50
