from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Protocol

from app.llm_tiers import (
    LlmTier,
    require_api_key,
    resolve_memory_provider,
    resolve_tier,
)
from app.subscribers.sub_llm.memory_category import classification_guidance, normalize_category
from app.workers.memory_timeline import format_chat_timeline, format_stt_timeline
from stream_store.models import TextRecord

_CATEGORY_GUIDANCE = classification_guidance()

SUMMARY_SYSTEM = f"""你是 Twitch 直播摘要助手。輸入為依時間排序的聊天室訊息（每行含 timestamp）。

請產生繁體中文摘要，**須依時間先後**描述本時段聊天動態（可條列 3-5 點，每點可標註約略時間）。
若訊息很少或無實質內容，簡短說明即可。

僅回傳 JSON（勿加 Markdown code fence）：{{"summary":"上述摘要","category":"fact|decision|progress|lore|gossip|discussion|chore"}}。
{_CATEGORY_GUIDANCE}"""

STT_SUMMARY_SYSTEM = f"""\
你是直播語音摘要助手。輸入為依時間排序的實況主 STT 轉錄（每行含 timestamp）。

請產生繁體中文摘要，**須依時間先後**描述實況主說了什麼（可條列 3-5 點，每點可標註約略時間）。
聚焦討論主題與重要決策；若內容零碎或無實質，簡短說明即可。

僅回傳 JSON（勿加 Markdown code fence）：{{"summary":"上述摘要","category":"fact|decision|progress|lore|gossip|discussion|chore"}}。
{_CATEGORY_GUIDANCE}"""

BOTH_SUMMARY_SYSTEM = f"""\
你是 Twitch 直播摘要助手。輸入同時包含同一時段的「聊天室訊息」與「實況主語音轉錄」，皆依時間排序（每行含 timestamp）。

請分別為兩者各產生一段繁體中文摘要，**須依時間先後**（可條列 3-5 點，每點可標註約略時間）。
chat 聚焦聊天室動態；stt 聚焦實況主說了什麼與重要決策。任一邊內容零碎或無實質時，該段簡短說明即可。

僅回傳 JSON（勿加 Markdown code fence），格式：
{{"chat":{{"summary":"聊天室摘要","category":"fact|decision|progress|lore|gossip|discussion|chore"}},"stt":{{"summary":"語音摘要","category":"fact|decision|progress|lore|gossip|discussion|chore"}}}}
{_CATEGORY_GUIDANCE}"""

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass(frozen=True)
class SummaryDraft:
    """L2 摘要產出：摘要正文與（可選）記憶分類。"""

    content: str
    category: str = ""


def parse_summary_response(raw: str) -> SummaryDraft:
    """解析 LLM 摘要輸出；支援 {summary, category} JSON，否則退回純文字（不分類）。"""
    text = raw.strip()
    if text.startswith("```"):
        text = _JSON_FENCE.sub("", text).strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            summary = str(data.get("summary", "")).strip()
            if summary:
                category_raw = data.get("category")
                category = normalize_category(category_raw) if category_raw else ""
                return SummaryDraft(content=summary, category=category)
    return SummaryDraft(content=raw.strip())


def _draft_from_section(section: object) -> SummaryDraft | None:
    if not isinstance(section, dict):
        return None
    summary = str(section.get("summary", "")).strip()
    if not summary:
        return None
    category_raw = section.get("category")
    category = normalize_category(category_raw) if category_raw else ""
    return SummaryDraft(content=summary, category=category)


def parse_both_response(raw: str) -> tuple[SummaryDraft, SummaryDraft] | None:
    """解析合併摘要輸出 {chat:{...}, stt:{...}}；任一段缺失即回 None（交由呼叫端 fallback）。"""
    text = raw.strip()
    if text.startswith("```"):
        text = _JSON_FENCE.sub("", text).strip()
    if not (text.startswith("{") and text.endswith("}")):
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    chat_draft = _draft_from_section(data.get("chat"))
    stt_draft = _draft_from_section(data.get("stt"))
    if chat_draft is None or stt_draft is None:
        return None
    return (chat_draft, stt_draft)


class Summarizer(Protocol):
    def summarize_chat(self, records: list[TextRecord]) -> SummaryDraft: ...

    def summarize_stt(self, records: list[TextRecord]) -> SummaryDraft: ...

    def summarize_both(
        self,
        chat_records: list[TextRecord],
        stt_records: list[TextRecord],
    ) -> tuple[SummaryDraft, SummaryDraft]: ...


class TemplateSummarizer:
    """無 LLM 的規則摘要；適合開發與測試。"""

    def summarize_chat(self, records: list[TextRecord]) -> SummaryDraft:
        if not records:
            return SummaryDraft("（本時段無聊天記錄）")
        lines = [
            f"【聊天室摘要（規則版）】時段 {records[0].timestamp} .. {records[-1].timestamp}",
            "",
        ]
        for record in records[:30]:
            lines.append(f"- [{record.timestamp}] {record.author}: {record.text[:120]}")
        if len(records) > 30:
            lines.append(f"- … 另有 {len(records) - 30} 則未列出")
        return SummaryDraft("\n".join(lines))

    def summarize_stt(self, records: list[TextRecord]) -> SummaryDraft:
        if not records:
            return SummaryDraft("（本時段無語音轉錄）")
        lines = [
            f"【實況語音摘要（規則版）】時段 {records[0].timestamp} .. {records[-1].timestamp}",
            "",
        ]
        for record in records[:30]:
            lines.append(f"- [{record.timestamp}] {record.text[:120]}")
        if len(records) > 30:
            lines.append(f"- … 另有 {len(records) - 30} 段未列出")
        return SummaryDraft("\n".join(lines))

    def summarize_both(
        self,
        chat_records: list[TextRecord],
        stt_records: list[TextRecord],
    ) -> tuple[SummaryDraft, SummaryDraft]:
        return (self.summarize_chat(chat_records), self.summarize_stt(stt_records))


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
    def from_env(cls, *, memory_backend: str | None = None) -> LlmSummarizer:
        backend = (
            memory_backend
            or os.environ.get("MEMORY_LLM_BACKEND", "openai")
            or "openai"
        ).lower()
        tier = resolve_tier(LlmTier.MEMORY, memory_backend=backend)
        require_api_key(tier)
        return cls(base_url=tier.base_url, api_key=tier.api_key, model=tier.model)

    def summarize_chat(self, records: list[TextRecord]) -> SummaryDraft:
        if not records:
            return SummaryDraft("（本時段無聊天記錄）")
        period = f"{records[0].timestamp} .. {records[-1].timestamp}"
        user_content = f"本時段：{period}\n\n" + format_chat_timeline(records)
        return parse_summary_response(self._complete(SUMMARY_SYSTEM, user_content))

    def summarize_stt(self, records: list[TextRecord]) -> SummaryDraft:
        if not records:
            return SummaryDraft("（本時段無語音轉錄）")
        period = f"{records[0].timestamp} .. {records[-1].timestamp}"
        user_content = f"本時段：{period}\n\n" + format_stt_timeline(records)
        return parse_summary_response(self._complete(STT_SUMMARY_SYSTEM, user_content))

    def summarize_both(
        self,
        chat_records: list[TextRecord],
        stt_records: list[TextRecord],
    ) -> tuple[SummaryDraft, SummaryDraft]:
        """單次 LLM 同時摘要 chat 與 stt；解析失敗時退回兩次獨立呼叫（不丟資料）。"""
        if not chat_records or not stt_records:
            return (self.summarize_chat(chat_records), self.summarize_stt(stt_records))
        all_records = sorted(chat_records + stt_records, key=lambda r: r.timestamp)
        period = f"{all_records[0].timestamp} .. {all_records[-1].timestamp}"
        user_content = (
            f"本時段：{period}\n\n"
            f"=== 聊天室 ===\n{format_chat_timeline(chat_records)}\n\n"
            f"=== 實況語音 ===\n{format_stt_timeline(stt_records)}"
        )
        parsed = parse_both_response(self._complete(BOTH_SUMMARY_SYSTEM, user_content))
        if parsed is not None:
            return parsed
        return (self.summarize_chat(chat_records), self.summarize_stt(stt_records))

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
        resolve_memory_provider(memory_backend=selected)
        return LlmSummarizer.from_env(memory_backend=selected)
    raise ValueError(f"unsupported MEMORY_LLM_BACKEND: {backend!r}")


def create_deep_summarizer(backend: str) -> Summarizer | None:
    """收台/手動深度摘要用的 summarizer（MEMORY_DEEP_MODEL，通常 Pro）。

    未設 MEMORY_DEEP_MODEL 或 backend 非 LLM 時回 None（深度觸發退回一般 summarizer）。
    """
    selected = backend.lower()
    if selected not in {"openai", "gemini"}:
        return None
    model = os.environ.get("MEMORY_DEEP_MODEL", "").strip()
    if not model:
        return None
    tier = resolve_tier(LlmTier.MEMORY, memory_backend=selected)
    require_api_key(tier)
    return LlmSummarizer(base_url=tier.base_url, api_key=tier.api_key, model=model)
