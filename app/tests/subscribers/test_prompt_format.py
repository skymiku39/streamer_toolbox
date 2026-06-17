from sub_llm.prompt_format import (
    compact_markdown,
    format_memory_snippet_for_prompt,
    join_sections,
    strip_memory_timestamp_header,
)


def test_compact_markdown_flattens_lists_and_headings() -> None:
    text = "## 回覆風格\n\n- 簡短友善\n- 繁體中文"
    assert compact_markdown(text) == "回覆風格 簡短友善 繁體中文"


def test_strip_memory_timestamp_header() -> None:
    doc = "[qa] 2026-06-17T17:36:47+00:00 .. 2026-06-17T17:36:47+00:00\n小甜甜是水果拼盤"
    assert strip_memory_timestamp_header(doc) == "小甜甜是水果拼盤"


def test_format_memory_snippet_for_prompt() -> None:
    doc = "[chat] 2026-06-12T10:00:00+00:00 .. 2026-06-12T10:05:00+00:00\n觀眾在聊 777"
    assert format_memory_snippet_for_prompt(doc) == "觀眾在聊 777"


def test_join_sections_skips_empty() -> None:
    assert join_sections("直播:狀態", "", "知識:梗") == "直播:狀態 | 知識:梗"
