from __future__ import annotations

import os

MODE_OFF = "off"
MODE_ON = "on"
MODE_AUTO = "auto"

_ON_VALUES = frozenset({"1", "true", "yes", "on"})

# auto 模式：問題帶下列即時性／時事關鍵字時，才認為值得動用 Google Search grounding。
# 免費層 grounding 每月額度有限（2.x 約 500 query），預設不替閒聊／既有知識問題開搜尋。
_REALTIME_KEYWORDS: tuple[str, ...] = (
    "今天",
    "今日",
    "現在",
    "目前",
    "最新",
    "剛剛",
    "剛才",
    "最近",
    "幾點",
    "新聞",
    "天氣",
    "股價",
    "匯率",
    "比分",
    "賽果",
    "上市",
    "發售",
    "更新了",
    "版本更新",
    "即時",
    "查一下",
    "搜尋",
    "google",
    "上網查",
    "查網路",
    "latest",
    "today",
    "news",
)


def resolve_web_search_mode(raw: str | None = None) -> str:
    """解析 LLM_WEB_SEARCH：off（永不）| on（每題）| auto（僅即時事實類）。

    未設或無法辨識時回 off（免費層安全預設）。
    """
    value = (raw if raw is not None else os.environ.get("LLM_WEB_SEARCH", "")).strip().lower()
    if value == MODE_AUTO:
        return MODE_AUTO
    if value in _ON_VALUES:
        return MODE_ON
    return MODE_OFF


def grounding_client_enabled(mode: str | None = None) -> bool:
    """factory 是否應建立可 grounding 的 client（on 或 auto 皆需要）。"""
    resolved = mode or resolve_web_search_mode()
    return resolved in {MODE_ON, MODE_AUTO}


def should_use_grounding(
    question: str,
    *,
    knowledge: str = "",
    game_reference: str = "",
    mode: str | None = None,
) -> tuple[bool, str]:
    """單題層級判斷是否動用 grounding，回傳 (是否搜尋, 原因標籤)。"""
    resolved = mode or resolve_web_search_mode()
    if resolved == MODE_OFF:
        return (False, "mode_off")
    if resolved == MODE_ON:
        return (True, "mode_on")

    text = question.strip().lower()
    if any(keyword in text for keyword in _REALTIME_KEYWORDS):
        return (True, "realtime_keyword")
    if not knowledge.strip() and not game_reference.strip():
        return (False, "no_signal")
    return (False, "covered_by_context")
