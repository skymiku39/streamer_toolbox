from __future__ import annotations

from typing import Protocol


class LlmClient(Protocol):
    def ask(
        self,
        question: str,
        *,
        context: str,
        knowledge: str = "",
        game_reference: str = "",
    ) -> str:
        """依問題、STT 上下文、知識庫與遊戲資料產出回覆文字。"""

    def generate_startup_greeting(
        self,
        *,
        channel: str,
        trigger_prefixes: tuple[str, ...],
    ) -> str:
        """程序上線時產出有趣、簡短的啟用宣告。"""


class TemplateLlmClient:
    """規則模板佔位實作；未連接外部 LLM API。"""

    def ask(
        self,
        question: str,
        *,
        context: str,
        knowledge: str = "",
        game_reference: str = "",
    ) -> str:
        context_hint = ""
        if context.strip():
            context_hint = "（已參考近期直播上下文）"
        knowledge_hint = ""
        if knowledge.strip():
            knowledge_hint = "（已參考知識庫）"
        game_hint = ""
        if game_reference.strip():
            game_hint = "（已參考遊戲資料）"
        return f"關於「{question}」：這是模擬回覆{context_hint}{knowledge_hint}{game_hint}。"

    def generate_startup_greeting(
        self,
        *,
        channel: str,
        trigger_prefixes: tuple[str, ...],
    ) -> str:
        del trigger_prefixes
        return (
            f"叮咚～AI 小助手已開機！在 {channel} 聊天室待命，"
            f"有問題可以用問號指令問我喔～"
        )
