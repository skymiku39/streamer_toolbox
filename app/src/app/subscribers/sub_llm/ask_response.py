from __future__ import annotations

import json
import re
from dataclasses import dataclass

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass(frozen=True)
class AskResponse:
    reply: str
    store_worthy: bool = False
    memory_value: int = 0
    memory_note: str = ""


def structured_output_guidance(max_content_chars: int | None = None) -> str:
    from sub_llm.config import DEFAULT_REPLY_MAX_LENGTH, resolve_reply_max_length

    limit = (
        max_content_chars
        if max_content_chars is not None
        else resolve_reply_max_length()
    )
    if limit <= 0:
        limit = DEFAULT_REPLY_MAX_LENGTH
    return (
        "【輸出格式】僅回傳 JSON（勿 Markdown code fence），欄位："
        '{"reply":"給觀眾的繁體回覆","store_worthy":true/false,'
        '"memory_value":1-5,"memory_note":"供日後 RAG 的精簡摘要（繁體）"}。'
        f"reply 正文不超過 {limit} 字（不含 @ 與標點），語意須完整收尾。"
        "store_worthy 僅在對本頻道後續有幫助時為 true（遊戲進度、頻道梗、主播決策）；"
        "通用百科、一次性測試、價值低者設 false 且 memory_value≤2。"
        "store_worthy 為 false 時 memory_note 可留空字串。"
    )


def gemini_ask_response_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "reply": {"type": "string"},
            "store_worthy": {"type": "boolean"},
            "memory_value": {"type": "integer"},
            "memory_note": {"type": "string"},
        },
        "required": ["reply", "store_worthy", "memory_value", "memory_note"],
    }


def parse_ask_response(raw: str) -> AskResponse:
    text = raw.strip()
    if not text:
        return AskResponse(reply="")

    if text.startswith("```"):
        text = _JSON_FENCE.sub("", text).strip()

    if text.startswith("{") and text.endswith("}"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            reply = str(data.get("reply", "")).strip()
            if reply:
                return AskResponse(
                    reply=reply,
                    store_worthy=bool(data.get("store_worthy", False)),
                    memory_value=max(0, int(data.get("memory_value", 0))),
                    memory_note=str(data.get("memory_note", "")).strip(),
                )

    return AskResponse(reply=text)
