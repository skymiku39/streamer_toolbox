from __future__ import annotations

import os

_BACKEND_LABELS = {
    "gemini": "Gemini",
    "openai": "OpenAI",
    "template": "Template",
}


def resolve_backend_label(backend: str | None = None) -> str:
    key = (backend or os.environ.get("LLM_BACKEND", "template") or "template").strip().lower()
    return _BACKEND_LABELS.get(key, key.upper())


def _classify_llm_error(exc: Exception) -> str:
    message = str(exc).lower()
    if isinstance(exc, ValueError) or "api_key" in message or "required" in message:
        return "credential_missing"
    if "401" in message or "403" in message or "unauthorized" in message:
        return "auth_failed"
    if "429" in message or "rate" in message:
        return "rate_limited"
    if "network" in message or "urlerror" in message or "timed out" in message:
        return "network"
    if type(exc).__name__ == "LlmApiError":
        return "api_error"
    return "unknown"


def build_template_startup_announcement(*, channel: str) -> str:
    """Template 佔位後端：未連接外部 LLM 推理服務時的啟動宣告。"""
    return (
        f"大家好，我是 {channel} 的 AI 助手。"
        f"目前系統以 Template 佔位後端運行，尚未連接 Gemini 等大型語言模型（LLM）推理端點；"
        f"問答僅供連線測試，正式推論需完成 API 憑證與端點設定。"
        f"設定完成後我就能正常回答囉！"
    )


def build_degraded_startup_announcement(
    *,
    channel: str,
    backend: str | None = None,
    error: Exception | None = None,
) -> str:
    """LLM 推理端點異常時的降級啟動宣告（仍發布至聊天室）。"""
    label = resolve_backend_label(backend)
    reason = _classify_llm_error(error) if error is not None else "unknown"

    if reason == "credential_missing":
        detail = f"{label} API 憑證（Credential）未設定或無效"
    elif reason == "auth_failed":
        detail = f"{label} 推理端點驗證失敗（HTTP 401/403）"
    elif reason == "rate_limited":
        detail = f"{label} 推理配額已用盡或觸發速率限制（Rate Limit）"
    elif reason == "network":
        detail = f"{label} 上游推理端點無法連線（Network / Timeout）"
    elif reason == "api_error":
        detail = f"{label} 推理 API 回傳錯誤（Upstream Error）"
    else:
        detail = f"{label} 推理服務暫時不可用（Degraded Mode）"

    return (
        f"大家好，我是 {channel} 的 AI 助手，程序已上線。"
        f"目前 LLM 推理端點未就緒：{detail}，系統以降級模式（Degraded Mode）運行；"
        f"生成式問答可能無法使用，請管理員檢查 LLM_BACKEND、API 金鑰與 LLM_API_BASE。"
    )
