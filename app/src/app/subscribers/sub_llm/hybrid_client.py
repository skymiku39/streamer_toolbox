from __future__ import annotations

import json
import os
import re
import sys

from sub_llm.ask_response import AskResponse
from sub_llm.openai_client import LlmApiError, OpenAiCompatibleLlmClient
from sub_llm.llm_backends import BACKEND_HYBRID, format_backend_log_tag
from sub_llm.prompts import resolve_system_prompt
from sub_llm.short_term_rag import SHORT_TERM_MARKER

_GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_AGENT_MODEL = "gemini-2.0-flash-lite"
DEFAULT_MAIN_MODEL = "gemini-2.5-flash"

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_AGENT_SYSTEM_PROMPT = (
    "你是直播問答的前置路由小助手。依據提供的『近期相似問答』判斷能否直接回答觀眾這次的問題。"
    "若近期問答已足以回答，輸出 {\"action\":\"answer\",\"reply\":\"繁體中文簡短回覆\"}；"
    "若資訊不足或需要更完整查證，輸出 {\"action\":\"escalate\",\"reply\":\"\"}。"
    "僅輸出 JSON，不要任何額外文字。"
)


def _parse_agent_decision(raw: str) -> tuple[str, str]:
    text = raw.strip()
    if text.startswith("```"):
        text = _JSON_FENCE.sub("", text).strip()
    if not (text.startswith("{") and text.endswith("}")):
        return ("escalate", "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return ("escalate", "")
    if not isinstance(data, dict):
        return ("escalate", "")
    action = str(data.get("action", "")).strip().lower()
    reply = str(data.get("reply", "")).strip()
    return (action, reply)


class HybridGeminiLlmClient:
    """Hybrid Agent 版：lite 小 Agent 路由 + flash 主 Gemini 回答。"""

    def __init__(
        self,
        *,
        agent_client: OpenAiCompatibleLlmClient,
        main_client: OpenAiCompatibleLlmClient,
    ) -> None:
        self._agent = agent_client
        self._main = main_client

    @classmethod
    def from_env(cls) -> HybridGeminiLlmClient:
        api_key = (
            os.environ.get("LLM_API_KEY")
            or os.environ.get("GOOGLE_AI_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or ""
        ).strip()
        if not api_key:
            raise ValueError(
                "GOOGLE_AI_API_KEY (或 LLM_API_KEY / GEMINI_API_KEY) is required"
            )
        base_url = (os.environ.get("LLM_API_BASE") or _GEMINI_OPENAI_BASE).strip()
        agent_model = (os.environ.get("LLM_AGENT_MODEL") or DEFAULT_AGENT_MODEL).strip()
        main_model = (
            os.environ.get("LLM_MODEL")
            or os.environ.get("GOOGLE_AI_MODEL")
            or DEFAULT_MAIN_MODEL
        ).strip()
        agent = OpenAiCompatibleLlmClient(
            base_url=base_url,
            api_key=api_key,
            model=agent_model,
            system_prompt=_AGENT_SYSTEM_PROMPT,
        )
        main = OpenAiCompatibleLlmClient(
            base_url=base_url,
            api_key=api_key,
            model=main_model,
            system_prompt=resolve_system_prompt(),
        )
        return cls(agent_client=agent, main_client=main)

    def ask(
        self,
        question: str,
        *,
        context: str,
        knowledge: str = "",
        game_reference: str = "",
        session_recap_reference: str = "",
    ) -> AskResponse:
        agent_reply = self._route_from_memory(question, knowledge=knowledge)
        tag = format_backend_log_tag(BACKEND_HYBRID)
        if agent_reply is not None:
            print(f"[sub-llm] {tag} action=answer", file=sys.stderr, flush=True)
            return AskResponse(reply=agent_reply)

        print(f"[sub-llm] {tag} action=escalate", file=sys.stderr, flush=True)
        return self._main.ask(
            question,
            context=context,
            knowledge=knowledge,
            game_reference=game_reference,
            session_recap_reference=session_recap_reference,
        )

    def generate_startup_greeting(
        self,
        *,
        channel: str,
        trigger_prefixes: tuple[str, ...],
    ) -> str:
        return self._main.generate_startup_greeting(
            channel=channel,
            trigger_prefixes=trigger_prefixes,
        )

    def _route_from_memory(self, question: str, *, knowledge: str) -> str | None:
        # 僅在已有短期記憶命中時才動用 lite agent，避免每題都多打一次 API。
        if SHORT_TERM_MARKER not in (knowledge or ""):
            return None
        messages = [
            {"role": "system", "content": _AGENT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"觀眾問題：{question.strip()}\n\n"
                    f"參考資料：\n{knowledge.strip()}\n\n"
                    "請判斷是否能僅憑上述近期問答直接回答。"
                ),
            },
        ]
        try:
            raw = self._agent.complete(messages, temperature=0.0, json_mode=True)
        except LlmApiError as exc:
            tag = format_backend_log_tag(BACKEND_HYBRID)
            print(
                f"[sub-llm] {tag} agent failed, escalate: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return None
        action, reply = _parse_agent_decision(raw)
        if action == "answer" and reply:
            return reply
        return None
