from __future__ import annotations

from typing import Protocol

from sub_llm.ask_response import AskResponse
from sub_llm.startup_messages import build_template_startup_announcement


class LlmClient(Protocol):
    def ask(
        self,
        question: str,
        *,
        context: str,
        knowledge: str = "",
        game_reference: str = "",
        session_recap_reference: str = "",
    ) -> AskResponse:
        """依問題、STT 上下文、知識庫、遊戲資料與本場回顧參考產出結構化回覆。"""

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
        session_recap_reference: str = "",
    ) -> AskResponse:
        from app.subscribers.qa_memory_mode import structured_ask_enabled

        context_hint = ""
        if context.strip():
            context_hint = "（已參考近期直播上下文）"
        knowledge_hint = ""
        if knowledge.strip():
            knowledge_hint = "（已參考知識庫）"
        game_hint = ""
        if game_reference.strip():
            game_hint = "（已參考遊戲資料）"
        recap_hint = ""
        if session_recap_reference.strip():
            recap_hint = "（已參考本場回顧）"
        reply = (
            f"關於「{question}」：這是模擬回覆"
            f"{context_hint}{knowledge_hint}{game_hint}{recap_hint}。"
        )
        if structured_ask_enabled():
            return AskResponse(
                reply=reply,
                store_worthy=False,
                memory_value=1,
                memory_note="",
            )
        return AskResponse(reply=reply)

    def generate_startup_greeting(
        self,
        *,
        channel: str,
        trigger_prefixes: tuple[str, ...],
    ) -> str:
        del trigger_prefixes
        return build_template_startup_announcement(channel=channel)
