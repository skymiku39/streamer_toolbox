from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

from sub_llm.ask_response import AskResponse, parse_ask_response
from app.subscribers.qa_memory_mode import structured_ask_enabled
from sub_llm.prompt_assembly import analyze_prompt_payload, build_ask_messages
from sub_llm.prompts import resolve_system_prompt
from sub_llm.startup_announcement import (
    _STARTUP_SYSTEM_PROMPT,
    build_startup_user_prompt,
)


class LlmApiError(RuntimeError):
    pass


class OpenAiCompatibleLlmClient:
    """OpenAI Chat Completions 相容客戶端（支援 OpenAI、Gemini OpenAI 相容端點、Ollama 等）。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str = "",
        timeout_sec: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._system_prompt = system_prompt.strip()
        self._timeout_sec = timeout_sec

    @classmethod
    def from_env(cls, *, backend: str | None = None) -> OpenAiCompatibleLlmClient:
        selected = (
            backend or os.environ.get("LLM_BACKEND", "openai") or "openai"
        ).lower()
        if selected == "gemini":
            base_url = os.environ.get(
                "LLM_API_BASE",
                "https://generativelanguage.googleapis.com/v1beta/openai",
            )
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
        else:
            base_url = (os.environ.get("LLM_API_BASE") or "https://api.openai.com/v1").strip()
            api_key = (os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
            model = (os.environ.get("LLM_MODEL") or "gpt-4o-mini").strip()
        system_prompt = resolve_system_prompt()
        if not api_key:
            if selected == "gemini":
                raise ValueError(
                    "GOOGLE_AI_API_KEY (或 LLM_API_KEY / GEMINI_API_KEY) is required"
                )
            raise ValueError("LLM_API_KEY (或 OPENAI_API_KEY) is required")
        return cls(
            base_url=base_url,
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
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
        if os.environ.get("LLM_DEBUG_PROMPT", "").strip().lower() in {"1", "true", "yes", "on"}:
            analysis = analyze_prompt_payload(
                question,
                context=context,
                knowledge=knowledge,
                game_reference=game_reference,
                system_prompt=self._system_prompt,
            )
            print(
                "[sub-llm] prompt "
                f"context_len={analysis['context_len']} "
                f"knowledge_len={analysis['knowledge_len']} "
                f"game_len={analysis['game_reference_len']} "
                f"stt={analysis['has_stt_marker']} "
                f"chat={analysis['has_chat_marker']} "
                f"game_ref={analysis['has_game_reference_marker']} "
                f"static_kb={analysis['has_static_kb_marker']} "
                f"memory={analysis['has_memory_marker']}",
                file=sys.stderr,
                flush=True,
            )

        raw = self._complete(messages, temperature=0.7)
        return parse_ask_response(raw)

    def generate_startup_greeting(
        self,
        *,
        channel: str,
        trigger_prefixes: tuple[str, ...],
    ) -> str:
        messages = [
            {"role": "system", "content": _STARTUP_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_startup_user_prompt(
                    channel=channel,
                    trigger_prefixes=trigger_prefixes,
                ),
            },
        ]
        return self._complete(messages, temperature=0.9)

    def _complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        if structured_ask_enabled():
            payload["response_format"] = {"type": "json_object"}
        response = self._post_json("chat/completions", payload)
        choices = response.get("choices", [])
        if not choices:
            raise LlmApiError("LLM response missing choices")
        message = choices[0].get("message", {})
        content = str(message.get("content", "")).strip()
        if not content:
            raise LlmApiError("LLM response missing message content")
        return content

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/{path.lstrip('/')}"
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_sec) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LlmApiError(f"LLM API failed ({exc.code}): {detail}") from exc
        except urllib.error.URLError as exc:
            raise LlmApiError(f"LLM API network error: {exc}") from exc
