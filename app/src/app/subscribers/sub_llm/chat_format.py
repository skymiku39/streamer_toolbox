from __future__ import annotations

import re

_FENCED_CODE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`]+)`")
_IMAGE_LINK = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_HEADER = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_BOLD_ITALIC = re.compile(r"\*\*\*([^*]+)\*\*\*")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_STRONG = re.compile(r"__([^_]+)__")
_ITALIC = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_EMPHASIS = re.compile(r"(?<!_)_([^_]+)_(?!_)")
_BLOCKQUOTE = re.compile(r"^>\s?", re.MULTILINE)
_HRULE = re.compile(r"^[-*_]{3,}\s*$", re.MULTILINE)
_EXCESS_BLANK = re.compile(r"\n{3,}")


def plain_text_for_chat(text: str) -> str:
    """將 LLM 常見 Markdown 輸出轉為 Twitch 聊天室可讀的純文字。"""
    result = text
    result = _FENCED_CODE.sub(r"\1", result)
    result = _INLINE_CODE.sub(r"\1", result)
    result = _IMAGE_LINK.sub(r"\1", result)
    result = _MARKDOWN_LINK.sub(r"\1", result)
    result = _HEADER.sub("", result)
    result = _BOLD_ITALIC.sub(r"\1", result)
    result = _BOLD.sub(r"\1", result)
    result = _STRONG.sub(r"\1", result)
    result = _ITALIC.sub(r"\1", result)
    result = _EMPHASIS.sub(r"\1", result)
    result = _BLOCKQUOTE.sub("", result)
    result = _HRULE.sub("", result)
    result = _EXCESS_BLANK.sub("\n\n", result)
    return result.strip()
