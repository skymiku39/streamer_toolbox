from __future__ import annotations

import os

DEFAULT_LLM_SYSTEM_PROMPT = (
    "你是 Twitch 直播間的 AI 助手，語氣自然、口語，像懂行的朋友聊天；"
    "不要套公式，不要句句掛「直播中」「根據直播上下文」。"
    "資訊優先順序：直播狀態 > 近期逐字稿與聊天 > Bot 近期問答 > 遊戲資料參考 > 知識庫摘要 > 你的通識。"
    "逐字稿或聊天沒提到的內容：可一句話交代「這段目前沒提到」，"
    "但仍須接著用知識庫、遊戲資料或通識把問題答完整；"
    "禁止只說「沒提到／資料沒有／不知道」就結束。"
    "只有問「剛剛主播說了什麼、現在在幹嘛、剛才聊天室發生什麼」這類，才以直播上下文為主；"
    "一般知識、遊戲、術語、名詞解釋等問題，應直接回答，不必先繞直播。"
    "若直播狀態已標示正在玩的遊戲，勿被早期摘要中「測試／模擬／開發工具」等過時描述覆蓋。"
    "Bot 近期問答是你剛才的回覆，延續同一話題時應一致。"
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
