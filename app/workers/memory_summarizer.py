from __future__ import annotations

from typing import Protocol

from pkg_stream_store.models import TextRecord

from app.workers.memory_timeline import format_merged_timeline, pair_qa_candidates

SUMMARY_SYSTEM = """你是 Twitch 直播摘要助手。根據聊天室訊息產生精簡摘要（繁體中文，條列 3-5 點）。
若訊息很少或無實質內容，簡短說明即可。"""

STT_SUMMARY_SYSTEM = """你是直播語音摘要助手。根據實況主 STT 轉錄文字產生精簡摘要（繁體中文，條列 3-5 點）。
聚焦實況主說了什麼、討論主題與重要決策；若內容零碎或無實質，簡短說明即可。"""

MERGED_SUMMARY_SYSTEM = """你是 Twitch 直播互動摘要助手。你會收到依時間排序的聊天室訊息（[CHAT]）與實況主語音轉錄（[STT]）。

請產生繁體中文摘要，**必須**包含：
1. 本時段整體主題與氛圍（2-3 句）
2. **問答對照**：依時間線配對「觀眾提問 ↔ 實況主回應」；若實況主先開話、觀眾後續回應也要標註
3. **待回覆**：觀眾已提問但實況主尚未回應的項目（若有）
4. **未接話**：實況主提起但聊天室尚未接話的話題（若有）

格式：總覽段落後，以「問答對照」「待回覆」「其他重點」等小標條列。"""


class Summarizer(Protocol):
    def summarize_chat(self, records: list[TextRecord]) -> str: ...

    def summarize_stt(self, records: list[TextRecord]) -> str: ...

    def summarize_merged(self, records: list[TextRecord]) -> str: ...


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

    def summarize_stt(self, records: list[TextRecord]) -> str:
        if not records:
            return "（本時段無語音轉錄）"
        lines = ["【實況語音摘要（規則版）】"]
        for record in records[:30]:
            lines.append(f"- [{record.timestamp}] {record.text[:120]}")
        if len(records) > 30:
            lines.append(f"- … 另有 {len(records) - 30} 段未列出")
        return "\n".join(lines)

    def summarize_merged(self, records: list[TextRecord]) -> str:
        if not records:
            return "（本時段無互動記錄）"
        lines = ["【直播互動摘要（規則版）】", "", "時序："]
        for line in format_merged_timeline(records).splitlines()[:40]:
            lines.append(f"- {line}")
        if len(records) > 40:
            lines.append(f"- … 另有 {len(records) - 40} 則未列出")

        pairs = pair_qa_candidates(records)
        if pairs:
            lines.extend(["", "問答對照（規則配對）："])
            for question, answer in pairs[:15]:
                q = f"{question.author}: {question.text[:80]}"
                if answer is not None:
                    lines.append(f"- Q {q}")
                    lines.append(f"  A 實況主: {answer.text[:80]}")
                else:
                    lines.append(f"- Q {q} → （待回覆）")
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
        chat_lines = [f"{record.author}: {record.text}" for record in records]
        user_content = "請摘要以下 Twitch 聊天室訊息：\n\n" + "\n".join(chat_lines)
        return self._complete(SUMMARY_SYSTEM, user_content)

    def summarize_stt(self, records: list[TextRecord]) -> str:
        if not records:
            return "（本時段無語音轉錄）"
        stt_lines = [f"[{record.timestamp}] {record.text}" for record in records]
        user_content = "請摘要以下實況主語音轉錄：\n\n" + "\n".join(stt_lines)
        return self._complete(STT_SUMMARY_SYSTEM, user_content)

    def summarize_merged(self, records: list[TextRecord]) -> str:
        if not records:
            return "（本時段無互動記錄）"
        timeline = format_merged_timeline(records)
        user_content = (
            "以下為依時間排序的直播互動紀錄（[CHAT]=觀眾聊天，[STT]=實況主語音）。"
            "請分析問答對照與待回覆項目：\n\n"
            + timeline
        )
        return self._complete(MERGED_SUMMARY_SYSTEM, user_content)

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
