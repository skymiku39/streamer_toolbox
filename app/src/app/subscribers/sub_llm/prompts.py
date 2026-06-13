from __future__ import annotations

import os

DEFAULT_LLM_SYSTEM_PROMPT = (
    "你是直播助手，請簡短回答觀眽問題。"
    "資訊來源優先順序：直播狀態 > 近期逐字稿與聊天 > Bot 近期問答 > 遊戲資料參考 > 知識庫摘要。"
    "若直播狀態已標示正在玩的遊戲，勿被早期摘要中「測試／模擬／開發工具」等過時描述覆蓋。"
    "Bot 近期問答列出你剛才回答過的問題與回覆，延續同一話題時應與之一致。"
    "若上述來源沒有相關資訊，可用你本身的常識補充，不要只回答「資料沒有」或「知識庫沒提到」。"
    "討論正在玩的遊戲時，可引用遊戲資料參考中的評分與簡介，勿捏造未提供的數字。"
    "勿捏造與直播主、頻道相關的未提供事實。"
    "勿使用 Markdown（無粗體、標題、連結語法），以純文字短句回覆，適合 Twitch 聊天室。"
)

_STRICT_KNOWLEDGE_ONLY_SUFFIX = (
    "僅能依據提供的直播上下文與知識庫回答；無相關資訊時請明確說不知道，勿使用其他常識。"
)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def resolve_system_prompt(raw: str | None = None) -> str:
    """組裝 sub-llm 系統提示；預設允許在 RAG 不足時使用模型自身知識。"""
    base = (raw if raw is not None else os.environ.get("LLM_SYSTEM_PROMPT", "")).strip()
    if not base:
        base = DEFAULT_LLM_SYSTEM_PROMPT
    if _env_bool("LLM_GENERAL_KNOWLEDGE", True):
        return base
    if _STRICT_KNOWLEDGE_ONLY_SUFFIX in base:
        return base
    return f"{base}{_STRICT_KNOWLEDGE_ONLY_SUFFIX}"
