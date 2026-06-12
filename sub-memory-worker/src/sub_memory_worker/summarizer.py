from __future__ import annotations

from typing import Protocol

from pkg_stream_store.models import TextRecord

SUMMARY_SYSTEM = """你是 Twitch 直播摘要助手。根據聊天室訊息產生精簡摘要（繁體中文，條列 3-5 點）。
若訊息很少或無實質內容，簡短說明即可。"""


class Summarizer(Protocol):
    def summarize_chat(self, records: list[TextRecord]) -> str: ...


class TemplateSummarizer:
    """無 LLM 的規則摘要；適合開發與測試。"""

    def summarize_chat(self, records: list[TextRecord]) -> str:
        if not records:
            return "（本時段無聊天記錄）"
        lines = ["【聊天室摘要（規則版）】"]
        for record in records[:30]:
            lines.append(f"- {record.author}: {record.text[:120]}")
        if len(records) > 30:
            lines.append(f"- … 另有 {len(records) - 30} 則未列出")
        return "\n".join(lines)


class LlmSummarizer:
    """OpenAI 相容 API 摘要（可接 Gemini OpenAI 端點）。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    @classmethod
    def from_env(cls) -> LlmSummarizer:
        import os

        backend = (os.environ.get("MEMORY_LLM_BACKEND", "openai") or "openai").lower()
        if backend == "gemini":
            base_url = os.environ.get(
                "LLM_API_BASE",
                "https://generativelanguage.googleapis.com/v1beta/openai",
            )
            api_key = (os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
            model = (os.environ.get("LLM_MODEL") or "gemini-2.0-flash").strip()
        else:
            base_url = (os.environ.get("LLM_API_BASE") or "https://api.openai.com/v1").strip()
            api_key = (os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
            model = (os.environ.get("LLM_MODEL") or "gpt-4o-mini").strip()
        if not api_key:
            raise ValueError("LLM_API_KEY is required for MEMORY_LLM_BACKEND=openai/gemini")
        return cls(base_url=base_url, api_key=api_key, model=model)

    def summarize_chat(self, records: list[TextRecord]) -> str:
        if not records:
            return "（本時段無聊天記錄）"
        chat_lines = [f"{record.author}: {record.text}" for record in records]
        user_content = "請摘要以下 Twitch 聊天室訊息：\n\n" + "\n".join(chat_lines)
        return self._complete(SUMMARY_SYSTEM, user_content)

    def _complete(self, system: str, user: str) -> str:
        import json
        import urllib.error
        import urllib.request

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.5,
        }
        url = f"{self._base_url}/chat/completions"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM summarize failed ({exc.code}): {detail}") from exc

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("LLM summarize response missing choices")
        content = str(choices[0].get("message", {}).get("content", "")).strip()
        if not content:
            raise RuntimeError("LLM summarize response missing content")
        return content


def create_summarizer(backend: str) -> Summarizer:
    selected = backend.lower()
    if selected == "template":
        return TemplateSummarizer()
    if selected in {"openai", "gemini"}:
        return LlmSummarizer.from_env()
    raise ValueError(f"unsupported MEMORY_LLM_BACKEND: {backend!r}")
