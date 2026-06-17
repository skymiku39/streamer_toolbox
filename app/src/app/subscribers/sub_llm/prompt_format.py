from __future__ import annotations

import re

INTRA_SEP = "·"
LINE_SEP = "\n"
GROUP_SEP = "\n\n"

LIVE_HEADER = "[直播]"
REF_HEADER = "[參考]"
QUESTION_HEADER = "[問題]"

PLACEHOLDER_MARKERS = ("[請填寫", "給編輯者", "bot 可忽略", "維護說明")

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
        stripped = stripped.replace("`", "").replace("**", "")
        parts.append(stripped)
    return squeeze_whitespace(" ".join(parts))


def strip_memory_timestamp_header(document: str) -> str:
    return MEMORY_HEADER_RE.sub("", document, count=1).strip()


def format_memory_snippet_for_prompt(document: str) -> str:
    return compact_markdown(strip_memory_timestamp_header(document))


def join_lines(*lines: str) -> str:
    return LINE_SEP.join(line.strip() for line in lines if line and line.strip())


def join_groups(*groups: str) -> str:
    return GROUP_SEP.join(group.strip() for group in groups if group and group.strip())


def is_placeholder_knowledge(text: str) -> bool:
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def filter_knowledge_for_prompt(knowledge: str) -> str:
    """剔除知識庫模板占位段落，保留可用片段。"""
    if not knowledge.strip():
        return ""
    kept: list[str] = []
    for line in knowledge.replace(" | ", LINE_SEP).splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("知識:"):
            _prefix, _sep, body = line.partition(":")
            chunks = [chunk.strip() for chunk in body.split(INTRA_SEP) if chunk.strip()]
            usable = [chunk for chunk in chunks if not is_placeholder_knowledge(chunk)]
            if usable:
                kept.append(f"知識:{INTRA_SEP.join(usable)}")
            continue
        if is_placeholder_knowledge(line):
            continue
        kept.append(line)
    return join_lines(*kept)


def build_user_prompt(
    question: str,
    *,
    context: str = "",
    knowledge: str = "",
    game_reference: str = "",
    session_recap_reference: str = "",
) -> str:
    """組裝 user 訊息：僅含事實上下文，規則與輸出格式應放 system。"""
    groups: list[str] = []
    if context.strip():
        groups.append(f"{LIVE_HEADER}{LINE_SEP}{context.strip()}")

    ref_lines: list[str] = []
    filtered_knowledge = filter_knowledge_for_prompt(knowledge)
    if filtered_knowledge:
        ref_lines.append(filtered_knowledge)
    if game_reference.strip():
        ref_lines.append(game_reference.strip())
    if session_recap_reference.strip():
        ref_lines.append(session_recap_reference.strip())
    if ref_lines:
        groups.append(f"{REF_HEADER}{LINE_SEP}{join_lines(*ref_lines)}")

    groups.append(f"{QUESTION_HEADER}{LINE_SEP}{question.strip()}")
    return join_groups(*groups)


def extract_block(user_content: str, header: str) -> str:
    if header not in user_content:
        return ""
    body = user_content.split(header, 1)[1]
    for next_header in (LIVE_HEADER, REF_HEADER, QUESTION_HEADER):
        if next_header == header:
            continue
        if next_header in body:
            body = body.split(next_header, 1)[0]
    return body.strip()
