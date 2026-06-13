from __future__ import annotations

from typing import Protocol


class LlmClient(Protocol):
    def ask(self, question: str, *, context: str, knowledge: str = "") -> str:
        """依問題、STT 上下文與知識庫產出回覆文字。"""


class TemplateLlmClient:
    """規則模板佔位實作；未連接外部 LLM API。"""

    def ask(self, question: str, *, context: str, knowledge: str = "") -> str:
        context_hint = ""
        if context.strip():
            context_hint = "（已參考近期直播上下文）"
        knowledge_hint = ""
        if knowledge.strip():
            knowledge_hint = "（已參考知識庫）"
        return f"關於「{question}」：這是模擬回覆{context_hint}{knowledge_hint}。"
