from __future__ import annotations

import re

# 高信心的提示詞注入樣式（中英並陳）。僅攔截明確的指令劫持，
# 一般含「指令」「規則」字眼的正常提問不應誤判，故樣式都要求「動詞 + 受詞」組合。
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"ignore\s+(?:all\s+|the\s+)?(?:previous|above|prior|earlier)\s+"
        r"(?:instructions?|prompts?|rules?|messages?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"disregard\s+(?:all\s+|the\s+)?(?:previous|above|prior)\s+"
        r"(?:instructions?|prompts?|rules?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"forget\s+(?:everything|all|your|the|previous)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:reveal|show|print|repeat|tell\s+me|expose|leak)\s+"
        r"(?:me\s+)?(?:your\s+)?(?:the\s+)?(?:system\s+)?(?:prompt|instructions?)",
        re.IGNORECASE,
    ),
    re.compile(r"\bsystem\s+prompt\b", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"pretend\s+(?:to\s+be|you\s+are|that\s+you)", re.IGNORECASE),
    re.compile(r"\b(?:developer\s+mode|jailbreak|\bDAN\b)\b", re.IGNORECASE),
    # 對話角色劫持：以 system:/assistant: 起手覆寫身分。
    re.compile(r"^\s*(?:system|assistant|developer)\s*[:：]", re.IGNORECASE),
    # 繁體中文常見注入
    re.compile(r"(?:忽略|無視|忽視|別管)(?:以上|之前|先前|上面|前面|所有)?(?:的)?(?:指令|指示|提示|規則|設定)"),
    re.compile(r"忘(?:記|掉)(?:你的|所有|先前|之前|剛剛)"),
    re.compile(r"(?:洩漏|洩露|顯示|告訴我|印出|公開)(?:你的)?(?:系統)?(?:提示詞?|指令|設定)"),
    re.compile(r"系統(?:提示詞?|指令)"),
    re.compile(r"你(?:現在)?(?:是|扮演|當)"),
    re.compile(r"(?:假裝|假設)你(?:是|現在)"),
    re.compile(r"開發者模式|越獄"),
)


def looks_like_injection(text: str) -> bool:
    """是否包含明確的提示詞注入／指令劫持樣式。"""
    stripped = text.strip()
    if not stripped:
        return False
    return any(pattern.search(stripped) for pattern in _INJECTION_PATTERNS)


class PromptInjectionFilter:
    """攔截觀眾輸入中的提示詞注入；輸出不檢查（沿用後續輸出安全層）。"""

    def filter_input(self, text: str) -> str | None:
        stripped = text.strip()
        if not stripped:
            return None
        if looks_like_injection(stripped):
            return None
        return stripped

    def filter_output(self, text: str) -> str | None:
        stripped = text.strip()
        return stripped if stripped else None
