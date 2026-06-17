from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

_GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
_OPENAI_BASE = "https://api.openai.com/v1"

DEFAULT_ASK_MODEL_GEMINI = "gemini-2.5-flash"
DEFAULT_ASK_MODEL_OPENAI = "gpt-4o-mini"
DEFAULT_AGENT_MODEL_GEMINI = "gemini-2.0-flash-lite"
DEFAULT_MEMORY_MODEL_GEMINI = "gemini-2.5-pro"
DEFAULT_MEMORY_MODEL_OPENAI = "gpt-4o"


class LlmProvider(str, Enum):
    GEMINI = "gemini"
    OPENAI = "openai"


class LlmTier(str, Enum):
    """LLM 用途分層：各層可獨立指定模型。"""

    ASK = "ask"
    AGENT = "agent"
    MEMORY = "memory"


@dataclass(frozen=True)
class TierLlmConfig:
    tier: LlmTier
    provider: LlmProvider
    model: str
    api_key: str
    base_url: str

    def log_label(self) -> str:
        return f"tier={self.tier.value} provider={self.provider.value} model={self.model}"


def resolve_gemini_api_key() -> str:
    return (
        os.environ.get("LLM_API_KEY")
        or os.environ.get("GOOGLE_AI_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or ""
    ).strip()


def resolve_openai_api_key() -> str:
    return (
        os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    ).strip()


def _first_env(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def resolve_ask_provider(*, ask_backend: str | None = None) -> LlmProvider:
    backend = (ask_backend or os.environ.get("LLM_BACKEND", "openai") or "openai").lower()
    if backend in {"gemini", "hybrid"}:
        return LlmProvider.GEMINI
    return LlmProvider.OPENAI


def resolve_memory_provider(*, memory_backend: str | None = None) -> LlmProvider:
    backend = (
        memory_backend or os.environ.get("MEMORY_LLM_BACKEND", "template") or "template"
    ).lower()
    if backend == "gemini":
        return LlmProvider.GEMINI
    if backend == "openai":
        return LlmProvider.OPENAI
    raise ValueError(
        f"MEMORY tier requires MEMORY_LLM_BACKEND=openai|gemini, got {backend!r}"
    )


def resolve_tier(
    tier: LlmTier,
    *,
    provider: LlmProvider | None = None,
    ask_backend: str | None = None,
    memory_backend: str | None = None,
) -> TierLlmConfig:
    """依用途分層解析模型與 API 設定。

    模型優先序（各層）：
    - ask:    LLM_ASK_MODEL → LLM_MODEL → GOOGLE_AI_MODEL
    - agent:  LLM_AGENT_MODEL
    - memory: MEMORY_LLM_MODEL → GOOGLE_AI_MEMORY_MODEL
    """
    if tier == LlmTier.ASK:
        resolved_provider = provider or resolve_ask_provider(ask_backend=ask_backend)
        if resolved_provider == LlmProvider.GEMINI:
            model = (
                _first_env("LLM_ASK_MODEL", "LLM_MODEL", "GOOGLE_AI_MODEL")
                or DEFAULT_ASK_MODEL_GEMINI
            )
            api_key = resolve_gemini_api_key()
            base_url = _first_env("LLM_API_BASE") or _GEMINI_OPENAI_BASE
        else:
            model = _first_env("LLM_ASK_MODEL", "LLM_MODEL") or DEFAULT_ASK_MODEL_OPENAI
            api_key = resolve_openai_api_key()
            base_url = _first_env("LLM_API_BASE") or _OPENAI_BASE
        return TierLlmConfig(
            tier=tier,
            provider=resolved_provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )

    if tier == LlmTier.AGENT:
        model = _first_env("LLM_AGENT_MODEL") or DEFAULT_AGENT_MODEL_GEMINI
        return TierLlmConfig(
            tier=tier,
            provider=LlmProvider.GEMINI,
            model=model,
            api_key=resolve_gemini_api_key(),
            base_url=_first_env("LLM_API_BASE") or _GEMINI_OPENAI_BASE,
        )

    if tier == LlmTier.MEMORY:
        resolved_provider = provider or resolve_memory_provider(
            memory_backend=memory_backend
        )
        if resolved_provider == LlmProvider.GEMINI:
            model = (
                _first_env("MEMORY_LLM_MODEL", "GOOGLE_AI_MEMORY_MODEL")
                or DEFAULT_MEMORY_MODEL_GEMINI
            )
            api_key = _first_env("MEMORY_LLM_API_KEY") or resolve_gemini_api_key()
            base_url = (
                _first_env("MEMORY_LLM_API_BASE", "LLM_API_BASE") or _GEMINI_OPENAI_BASE
            )
        else:
            model = _first_env("MEMORY_LLM_MODEL") or DEFAULT_MEMORY_MODEL_OPENAI
            api_key = _first_env("MEMORY_LLM_API_KEY") or resolve_openai_api_key()
            base_url = _first_env("MEMORY_LLM_API_BASE", "LLM_API_BASE") or _OPENAI_BASE
        return TierLlmConfig(
            tier=tier,
            provider=resolved_provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )

    raise ValueError(f"unsupported tier: {tier!r}")


def require_api_key(config: TierLlmConfig) -> None:
    if config.api_key:
        return
    if config.provider == LlmProvider.GEMINI:
        raise ValueError(
            "GOOGLE_AI_API_KEY (或 LLM_API_KEY / GEMINI_API_KEY) is required"
        )
    raise ValueError("LLM_API_KEY (或 OPENAI_API_KEY) is required")


def format_sub_llm_tier_log(*, ask_backend: str) -> str:
    backend = ask_backend.lower()
    if backend == "template":
        return "tiers=template"
    if backend == "hybrid":
        agent = resolve_tier(LlmTier.AGENT)
        ask = resolve_tier(LlmTier.ASK, ask_backend=backend)
        return f"tiers agent={agent.model} ask={ask.model}"
    ask = resolve_tier(LlmTier.ASK, ask_backend=backend)
    return f"tiers ask={ask.model}"
