from __future__ import annotations


def period_end_from_snippet(document: str, metadata: dict[str, str] | None = None) -> str:
    """從 Chroma metadata 或摘要文件首行解析 period_end。"""
    if metadata and metadata.get("period_end"):
        return str(metadata["period_end"])
    first_line = document.split("\n", 1)[0].strip()
    if " .. " in first_line:
        return first_line.rsplit(" .. ", 1)[-1].strip()
    return ""


def rank_memory_snippets(
    documents: list[str],
    metadatas: list[dict[str, str]] | None = None,
) -> list[str]:
    """依 period_end 由新到舊排序，去除重複片段。"""
    meta_list = metadatas or [{} for _ in documents]
    pairs: list[tuple[str, str]] = []
    for doc, meta in zip(documents, meta_list, strict=False):
        stripped = (doc or "").strip()
        if not stripped:
            continue
        pairs.append((stripped, period_end_from_snippet(stripped, meta)))

    pairs.sort(key=lambda item: item[1], reverse=True)
    unique: list[str] = []
    seen: set[str] = set()
    for doc, _ in pairs:
        if doc in seen:
            continue
        seen.add(doc)
        unique.append(doc)
    return unique
