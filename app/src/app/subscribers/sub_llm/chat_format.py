from __future__ import annotations

import re
import unicodedata

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
_CHAT_TAG = re.compile(r"@[A-Za-z0-9_]+|#[A-Za-z0-9_]+")


def _is_non_content_char(ch: str) -> bool:
    if ch.isspace():
        return True
    category = unicodedata.category(ch)
    return category.startswith(("P", "S", "Z"))


def count_reply_content_chars(text: str) -> int:
    """計算回覆正文長度：不含 @/# tag 與標點、空白。"""
    count = 0
    index = 0
    while index < len(text):
        tag = _CHAT_TAG.match(text, index)
        if tag:
            index = tag.end()
            continue
        char = text[index]
        if not _is_non_content_char(char):
            count += 1
        index += 1
    return count


def truncate_reply_for_chat(text: str, max_content_chars: int) -> str:
    """截斷回覆，使正文不超過 max_content_chars（不含 tag 與標點）。"""
    if max_content_chars <= 0:
        return ""
    if count_reply_content_chars(text) <= max_content_chars:
        return text

    parts: list[str] = []
    content_count = 0
    index = 0
    while index < len(text):
        tag = _CHAT_TAG.match(text, index)
        if tag:
            parts.append(tag.group())
            index = tag.end()
            continue
        char = text[index]
        if _is_non_content_char(char):
            parts.append(char)
            index += 1
            continue
        if content_count >= max_content_chars:
            break
        parts.append(char)
        content_count += 1
        index += 1
    return "".join(parts).strip()


def cap_reply_for_chat(text: str, max_content_chars: int) -> str:
    """將 LLM 回覆限制在聊天室可接受的正文長度內。"""
    return truncate_reply_for_chat(text.strip(), max_content_chars)


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
