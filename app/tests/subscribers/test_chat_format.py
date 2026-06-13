from sub_llm.chat_format import plain_text_for_chat


def test_strips_bold_and_italic() -> None:
    assert plain_text_for_chat("**重點**與*斜體*") == "重點與斜體"
    assert plain_text_for_chat("__粗體__與_斜體_") == "粗體與斜體"


def test_strips_headers_and_links() -> None:
    text = "## 標題\n請看[官方文件](https://example.com)"
    assert plain_text_for_chat(text) == "標題\n請看官方文件"


def test_strips_code_and_blockquote() -> None:
    text = "> 引用\n`code` 與\n```py\nprint('hi')\n```"
    assert plain_text_for_chat(text) == "引用\ncode 與\nprint('hi')"
