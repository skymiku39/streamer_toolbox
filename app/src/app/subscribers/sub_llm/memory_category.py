"""記憶分類（category）：決定檢索時的可信度、排序與標註。

保留與否仍以 RAG 價值門檻（store_worthy / memory_value）為主；
category 不阻擋寫入，只在讀取時控制「能否當事實、衝突時誰優先、如何標註」。
"""

from __future__ import annotations

CATEGORY_FACT = "fact"
CATEGORY_DECISION = "decision"
CATEGORY_PROGRESS = "progress"
CATEGORY_LORE = "lore"
CATEGORY_GOSSIP = "gossip"
CATEGORY_DISCUSSION = "discussion"
CATEGORY_CHORE = "chore"

# 未分類時的安全預設：最低可信度，避免被當事實。
DEFAULT_CATEGORY = CATEGORY_DISCUSSION

VALID_CATEGORIES: frozenset[str] = frozenset(
    {
        CATEGORY_FACT,
        CATEGORY_DECISION,
        CATEGORY_PROGRESS,
        CATEGORY_LORE,
        CATEGORY_GOSSIP,
        CATEGORY_DISCUSSION,
        CATEGORY_CHORE,
    }
)

# 可信度排序（數字越大越權威）；檢索時據此排序並決定衝突優先。
_TRUST_RANK: dict[str, int] = {
    CATEGORY_FACT: 5,
    CATEGORY_DECISION: 4,
    CATEGORY_PROGRESS: 3,
    CATEGORY_LORE: 3,
    CATEGORY_DISCUSSION: 1,
    CATEGORY_GOSSIP: 0,
    CATEGORY_CHORE: 0,
}

# 事實級：可單獨支撐一個肯定句的回答。
FACTUAL_CATEGORIES: frozenset[str] = frozenset(
    {CATEGORY_FACT, CATEGORY_DECISION, CATEGORY_PROGRESS, CATEGORY_LORE}
)
# 低可信度：永遠不可當事實，僅供語氣／參考。
LOW_TRUST_CATEGORIES: frozenset[str] = frozenset(
    {CATEGORY_GOSSIP, CATEGORY_DISCUSSION}
)

# 精簡標籤（配合精簡 prompt 風格）。
_LABELS: dict[str, str] = {
    CATEGORY_FACT: "事實",
    CATEGORY_DECISION: "決策",
    CATEGORY_PROGRESS: "進度",
    CATEGORY_LORE: "梗",
    CATEGORY_GOSSIP: "八卦",
    CATEGORY_DISCUSSION: "討論",
    CATEGORY_CHORE: "雜訊",
}

# 非 qa 來源（chat/stt 為主播實況摘要）視為進度級可信度。
_SOURCE_FALLBACK_TRUST: dict[str, int] = {
    "chat": _TRUST_RANK[CATEGORY_PROGRESS],
    "stt": _TRUST_RANK[CATEGORY_PROGRESS],
}


def normalize_category(value: str | None) -> str:
    """轉成合法 category；空值或無法辨識者回傳預設（最低可信度）。"""
    if not value:
        return DEFAULT_CATEGORY
    candidate = value.strip().lower()
    return candidate if candidate in VALID_CATEGORIES else DEFAULT_CATEGORY


def trust_rank(category: str | None) -> int:
    return _TRUST_RANK.get(normalize_category(category), 0)


def effective_trust(category: str | None, source: str | None = None) -> int:
    """檢索排序用：category 缺漏時依來源（chat/stt）回退到進度級。"""
    raw = (category or "").strip().lower()
    if raw in VALID_CATEGORIES:
        return _TRUST_RANK[raw]
    if source:
        fallback = _SOURCE_FALLBACK_TRUST.get(source.strip().lower())
        if fallback is not None:
            return fallback
    return _TRUST_RANK[DEFAULT_CATEGORY]


def is_factual(category: str | None) -> bool:
    return normalize_category(category) in FACTUAL_CATEGORIES


def is_low_trust(category: str | None) -> bool:
    return normalize_category(category) in LOW_TRUST_CATEGORIES


def category_label(category: str | None) -> str:
    return _LABELS.get(normalize_category(category), _LABELS[DEFAULT_CATEGORY])


def classification_guidance() -> str:
    """供 LLM 結構化輸出的分類指引（精簡）。"""
    return (
        "category 擇一標註此問答記憶分類："
        "fact=頻道/主播穩定事實(設備/排程/連結/規則)；"
        "decision=主播當下宣告的計畫或決定；"
        "progress=本場遊戲/工作進度；"
        "lore=頻道固定梗/暱稱/文化；"
        "gossip=關係臆測/起鬨/八卦(不可當事實)；"
        "discussion=主觀意見/閒聊/辯論；"
        "chore=一次性測試/通用百科/灌水。"
    )
