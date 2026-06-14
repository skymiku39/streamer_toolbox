from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

from sub_llm.ask_response import (
    AskResponse,
    gemini_ask_response_schema,
    parse_ask_response,
)
from app.subscribers.qa_memory_mode import structured_ask_enabled
from sub_llm.openai_client import LlmApiError, OpenAiCompatibleLlmClient
from sub_llm.prompt_assembly import build_ask_messages
from sub_llm.prompts import resolve_system_prompt

_SIMPLIFIED_ONLY = frozenset(
    "这时为发对还会来个个与关开问样让认识读写语请谢爱类组织报导联系网页测试产品应该总体学现将较称码视频导标题连接击览载规则删编辑复杂简单变区没说过说种动国点线号电话录储库帮门关键选择启动运行设置参数输入输出处理错误异常详细东马风龙鱼鸟汉边进远钟铁银钱买卖价质气阳阴书画药医师严欢乐"
)


def _detect_simplified_chars(text: str) -> list[str]:
    return sorted({ch for ch in text if ch in _SIMPLIFIED_ONLY})


def _agent_debug_log(*, hypothesis_id: str, location: str, message: str, data: dict[str, Any]) -> None:
    # #region agent log
    try:
        import time

        payload = {
            "sessionId": "6897dd",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open("debug-6897dd.log", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass
    # #endregion


class GeminiGroundedLlmClient:
    """Gemini 原生 generateContent + Google Search grounding。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        system_prompt: str = "",
        timeout_sec: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._system_prompt = system_prompt.strip()
        self._timeout_sec = timeout_sec
        self._fallback = OpenAiCompatibleLlmClient(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            timeout_sec=timeout_sec,
        )

    @classmethod
    def from_env(cls) -> GeminiGroundedLlmClient:
        api_key = (
            os.environ.get("LLM_API_KEY")
            or os.environ.get("GOOGLE_AI_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or ""
        ).strip()
        model = (
            os.environ.get("LLM_MODEL")
            or os.environ.get("GOOGLE_AI_MODEL")
            or "gemini-2.5-flash"
        ).strip()
        if not api_key:
            raise ValueError(
                "GOOGLE_AI_API_KEY (或 LLM_API_KEY / GEMINI_API_KEY) is required"
            )
        return cls(
            api_key=api_key,
            model=model,
            system_prompt=resolve_system_prompt(),
        )

    def ask(
        self,
        question: str,
        *,
        context: str,
        knowledge: str = "",
        game_reference: str = "",
    ) -> AskResponse:
        messages = build_ask_messages(
            question,
            context=context,
            knowledge=knowledge,
            game_reference=game_reference,
            system_prompt=self._system_prompt,
        )
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        system_content = next(
            (m["content"] for m in messages if m["role"] == "system"),
            self._system_prompt,
        )
        try:
            raw = self._generate_with_google_search(
                system_content,
                user_content,
            )
            print(
                "[sub-llm] gemini google_search grounding used",
                file=sys.stderr,
                flush=True,
            )
            parsed = parse_ask_response(raw)
            # #region agent log
            _agent_debug_log(
                hypothesis_id="A,B,C",
                location="gemini_grounded.py:ask",
                message="llm reply script audit",
                data={
                    "system_has_trad_rule": "繁體中文" in system_content,
                    "user_has_trad_guidance": "繁體中文" in user_content,
                    "knowledge_simplified": _detect_simplified_chars(knowledge),
                    "reply_simplified": _detect_simplified_chars(parsed.reply),
                    "reply_preview": parsed.reply[:120],
                    "store_worthy": parsed.store_worthy,
                    "memory_value": parsed.memory_value,
                },
            )
            # #endregion
            return parsed
        except LlmApiError as exc:
            print(
                f"[sub-llm] google_search failed, fallback to chat: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return self._fallback.ask(
                question,
                context=context,
                knowledge=knowledge,
                game_reference=game_reference,
            )

    def generate_startup_greeting(
        self,
        *,
        channel: str,
        trigger_prefixes: tuple[str, ...],
    ) -> str:
        return self._fallback.generate_startup_greeting(
            channel=channel,
            trigger_prefixes=trigger_prefixes,
        )

    def _generate_with_google_search(self, system: str, user: str) -> str:
        generation_config: dict[str, Any] = {"temperature": 0.7}
        if structured_ask_enabled():
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseSchema"] = gemini_ask_response_schema()
        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": generation_config,
        }
        model_path = self._model
        if not model_path.startswith("models/"):
            model_path = f"models/{model_path}"
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/{model_path}"
            ":generateContent"
        )
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "x-goog-api-key": self._api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_sec) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LlmApiError(f"Gemini grounding failed ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise LlmApiError(f"Gemini grounding network error: {exc}") from exc

        candidates = data.get("candidates", [])
        if not candidates:
            raise LlmApiError("Gemini grounding response missing candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        texts = [str(part.get("text", "")).strip() for part in parts if part.get("text")]
        content = "\n".join(text for text in texts if text).strip()
        if not content:
            raise LlmApiError("Gemini grounding response missing text")
        return content
