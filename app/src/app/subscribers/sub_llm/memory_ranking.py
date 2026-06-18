from __future__ import annotations

from sub_llm.memory_category import effective_trust

# 混合排序權重：以語意相關度為主、記憶可信度為輔。
_RELEVANCE_WEIGHT = 0.7
_TRUST_WEIGHT = 0.3
# trust_rank 上限（fact=5），用於把可信度正規化到 [0, 1]。
_MAX_TRUST = 5.0


def _similarity_from_distance(distance: float | None) -> float:
    """將 Chroma cosine distance 轉成 [0, 1] 的相似度；None 視為最低相似度。"""
    if distance is None:
        return 0.0
    sim = 1.0 - float(distance)
    if sim < 0.0:
        return 0.0
    if sim > 1.0:
        return 1.0
    return sim


def _hybrid_score(distance: float | None, trust: int) -> float:
    similarity = _similarity_from_distance(distance)
    trust_norm = max(0.0, min(1.0, trust / _MAX_TRUST))
    return _RELEVANCE_WEIGHT * similarity + _TRUST_WEIGHT * trust_norm


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
    distances: list[float | None] | None = None,
) -> list[str]:
    """混合排序並去重。

    - 有提供 distances（Chroma 相似度）時：以「語意相關度為主、可信度為輔」的
      混合分數排序，同分再依 period_end 由新到舊。
    - 未提供 distances 時：沿用「可信度優先、同級再依時間」的排序，確保無向量
      分數時（如 fallback／測試）行為不變。
    """
    meta_list = metadatas or [{} for _ in documents]
    dist_list = distances if distances is not None else [None] * len(documents)
    items: list[tuple[str, int, str, float | None]] = []
    for doc, meta, dist in zip(documents, meta_list, dist_list, strict=False):
        stripped = (doc or "").strip()
        if not stripped:
            continue
        meta = meta or {}
        trust = effective_trust(meta.get("category"), meta.get("source"))
        items.append((stripped, trust, period_end_from_snippet(stripped, meta), dist))

    has_distance = any(dist is not None for *_, dist in items)
    if has_distance:
        # 相關度為主、可信度為輔；同分再依時間（新→舊）。
        items.sort(key=lambda item: (_hybrid_score(item[3], item[1]), item[2]), reverse=True)
    else:
        # 可信度（高→低）優先，同級再依時間（新→舊）。
        items.sort(key=lambda item: (item[1], item[2]), reverse=True)

    unique: list[str] = []
    seen: set[str] = set()
    for doc, *_ in items:
        if doc in seen:
            continue
        seen.add(doc)
        unique.append(doc)
    return unique
