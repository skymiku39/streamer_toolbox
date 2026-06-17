from __future__ import annotations

import os
from dataclasses import dataclass

# LLM 問答後端命名（技術 ID ↔ 產品名稱）
# 注意：與 control-plane「T4 Hybrid STT」無關；此處 hybrid 指 LLM Hybrid Agent 問答模式。

BACKEND_TEMPLATE = "template"
BACKEND_OPENAI = "openai"
BACKEND_GEMINI = "gemini"
BACKEND_HYBRID = "hybrid"

VALID_LLM_BACKENDS = frozenset(
    {BACKEND_TEMPLATE, BACKEND_OPENAI, BACKEND_GEMINI, BACKEND_HYBRID}
)


@dataclass(frozen=True)
class LlmBackendInfo:
    """單一 LLM 後端的中英文識別與簡述。"""

    backend_id: str
    display_name: str
    slug: str
    summary: str


_LLM_BACKENDS: dict[str, LlmBackendInfo] = {
    BACKEND_TEMPLATE: LlmBackendInfo(
        backend_id=BACKEND_TEMPLATE,
        display_name="Template 佔位",
        slug="template-stub",
        summary="無外部 LLM，假回覆供連線測試",
    ),
    BACKEND_OPENAI: LlmBackendInfo(
        backend_id=BACKEND_OPENAI,
        display_name="OpenAI 相容",
        slug="openai-compat",
        summary="OpenAI Chat Completions 相容端點",
    ),
    BACKEND_GEMINI: LlmBackendInfo(
        backend_id=BACKEND_GEMINI,
        display_name="Gemini 直連",
        slug="gemini-direct",
        summary="單段式 Gemini 問答；預設可啟用 Google Search grounding",
    ),
    BACKEND_HYBRID: LlmBackendInfo(
        backend_id=BACKEND_HYBRID,
        display_name="Hybrid Agent",
        slug="hybrid-agent",
        summary="小 Agent（lite）路由 + 雲端 Gemini（flash）主回答；含短期 RAG 與流程管控",
    ),
}


def normalize_backend_id(backend: str | None = None) -> str:
    key = (backend or os.environ.get("LLM_BACKEND", BACKEND_TEMPLATE) or BACKEND_TEMPLATE)
    return key.strip().lower()


def resolve_backend_info(backend: str | None = None) -> LlmBackendInfo:
    key = normalize_backend_id(backend)
    return _LLM_BACKENDS.get(
        key,
        LlmBackendInfo(
            backend_id=key,
            display_name=key.upper(),
            slug=key,
            summary="",
        ),
    )


def resolve_backend_label(backend: str | None = None) -> str:
    """啟動宣告、降級訊息等使用的顯示名稱。"""
    return resolve_backend_info(backend).display_name


def format_backend_log_tag(backend: str | None = None) -> str:
    """stderr log 前綴，例如 Hybrid Agent（hybrid-agent）。"""
    info = resolve_backend_info(backend)
    return f"{info.display_name}（{info.slug}）"


def argparse_backend_help() -> str:
    parts = [
        f"{info.backend_id}＝{info.display_name}：{info.summary}"
        for info in _LLM_BACKENDS.values()
    ]
    return "LLM 後端：" + "；".join(parts)


def is_hybrid_agent_backend(backend: str | None = None) -> bool:
    return normalize_backend_id(backend) == BACKEND_HYBRID


def is_gemini_direct_backend(backend: str | None = None) -> bool:
    return normalize_backend_id(backend) == BACKEND_GEMINI
