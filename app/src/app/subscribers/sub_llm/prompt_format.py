from __future__ import annotations

import re

SECTION_SEP = " | "
INTRA_SEP = "·"

MEMORY_HEADER_RE = re.compile(
    r"^\[(?:qa|chat|stt)\]\s+[^\n]+?\s+\.\.\s+[^\n]+\n?",
    re.MULTILINE,
)


def squeeze_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def compact_markdown(text: str) -> str:
    """將知識庫／摘要片段壓成單行，移除多餘 Markdown 裝飾。"""
    parts: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        if stripped.startswith("- "):
            stripped = stripped[2:].strip()
        if stripped.startswith(">"):
            stripped = stripped.lstrip(">").strip()
        stripped = stripped.replace("`", "")
        parts.append(stripped)
    return squeeze_whitespace(" ".join(parts))


def strip_memory_timestamp_header(document: str) -> str:
    return MEMORY_HEADER_RE.sub("", document, count=1).strip()


def format_memory_snippet_for_prompt(document: str) -> str:
    return compact_markdown(strip_memory_timestamp_header(document))


def join_sections(*sections: str) -> str:
    return SECTION_SEP.join(section.strip() for section in sections if section and section.strip())
