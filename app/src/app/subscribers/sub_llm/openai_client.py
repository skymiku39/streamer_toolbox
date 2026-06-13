from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


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
        system_prompt = (os.environ.get("LLM_SYSTEM_PROMPT") or "").strip()
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

    def ask(self, question: str, *, context: str, knowledge: str = "") -> str:
        messages: list[dict[str, str]] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        user_sections: list[str] = []
        if context.strip():
            user_sections.append(f"近期直播上下文：\n{context.strip()}")
        if knowledge.strip():
            user_sections.append(f"知識庫參考：\n{knowledge.strip()}")
        user_sections.append(f"觀眾問題：{question.strip()}")
        messages.append({"role": "user", "content": "\n\n".join(user_sections)})

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.7,
        }
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
