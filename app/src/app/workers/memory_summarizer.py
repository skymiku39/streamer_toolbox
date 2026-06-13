from __future__ import annotations

from typing import Protocol

from stream_store.models import TextRecord

from app.workers.memory_timeline import format_chat_timeline, format_stt_timeline

SUMMARY_SYSTEM = """你是 Twitch 直播摘要助手。輸入為依時間排序的聊天室訊息（每行含 timestamp）。

請產生繁體中文摘要，**須依時間先後**描述本時段聊天動態（可條列 3-5 點，每點可標註約略時間）。
若訊息很少或無實質內容，簡短說明即可。"""

STT_SUMMARY_SYSTEM = """你是直播語音摘要助手。輸入為依時間排序的實況主 STT 轉錄（每行含 timestamp）。

請產生繁體中文摘要，**須依時間先後**描述實況主說了什麼（可條列 3-5 點，每點可標註約略時間）。
聚焦討論主題與重要決策；若內容零碎或無實質，簡短說明即可。"""


class Summarizer(Protocol):
    def summarize_chat(self, records: list[TextRecord]) -> str: ...

    def summarize_stt(self, records: list[TextRecord]) -> str: ...


class TemplateSummarizer:
    """無 LLM 的規則摘要；適合開發與測試。"""

    def summarize_chat(self, records: list[TextRecord]) -> str:
        if not records:
            return "（本時段無聊天記錄）"
        lines = [
            f"【聊天室摘要（規則版）】時段 {records[0].timestamp} .. {records[-1].timestamp}",
            "",
        ]
        for record in records[:30]:
            lines.append(f"- [{record.timestamp}] {record.author}: {record.text[:120]}")
        if len(records) > 30:
            lines.append(f"- … 另有 {len(records) - 30} 則未列出")
        return "\n".join(lines)

    def summarize_stt(self, records: list[TextRecord]) -> str:
        if not records:
            return "（本時段無語音轉錄）"
        lines = [
            f"【實況語音摘要（規則版）】時段 {records[0].timestamp} .. {records[-1].timestamp}",
            "",
        ]
        for record in records[:30]:
            lines.append(f"- [{record.timestamp}] {record.text[:120]}")
        if len(records) > 30:
            lines.append(f"- … 另有 {len(records) - 30} 段未列出")
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
        if not api_key:
            raise ValueError(
                "GOOGLE_AI_API_KEY (或 LLM_API_KEY / GEMINI_API_KEY) is required "
                "for MEMORY_LLM_BACKEND=openai/gemini"
            )
        return cls(base_url=base_url, api_key=api_key, model=model)

    def summarize_chat(self, records: list[TextRecord]) -> str:
        if not records:
            return "（本時段無聊天記錄）"
        period = f"{records[0].timestamp} .. {records[-1].timestamp}"
        user_content = f"本時段：{period}\n\n" + format_chat_timeline(records)
        return self._complete(SUMMARY_SYSTEM, user_content)

    def summarize_stt(self, records: list[TextRecord]) -> str:
        if not records:
            return "（本時段無語音轉錄）"
        period = f"{records[0].timestamp} .. {records[-1].timestamp}"
        user_content = f"本時段：{period}\n\n" + format_stt_timeline(records)
        return self._complete(STT_SUMMARY_SYSTEM, user_content)

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
