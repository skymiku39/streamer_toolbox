"""常用 process 組合，避免漏跑 ingress-twitch-stream 等相依程序。"""

from __future__ import annotations

STACK_INGRESS = (
    "ingress-ttv-read",
    "ingress-twitch-audio",
    "ingress-twitch-stream",
    "sub-stream-record",
)

# GCP / 純文字 AI 問答：不含 STT（見 deploy/docker-compose.gcp.yml）
STACK_INGRESS_CHAT = (
    "ingress-ttv-read",
    "ingress-twitch-stream",
    "sub-stream-record",
)

STACK_LLM = (
    "sub-llm",
    "sub-qa-memory-structured",
    "sub-qa-memory-batch",
    "twitch-connector",
)

# 僅發布直播狀態至聊天室（不含 !ask 問答）；需搭配 --stack ingress 收 metadata。
STACK_STATUS = (
    "sub-live-status",
    "twitch-connector",
)

PROCESS_STACKS: dict[str, tuple[str, ...]] = {
    "ingress": STACK_INGRESS,
    "ingress-chat": STACK_INGRESS_CHAT,
    "status": STACK_STATUS,
    "llm": STACK_LLM,
}


def resolve_stack(name: str) -> list[str]:
    key = name.strip().lower()
    try:
        return list(PROCESS_STACKS[key])
    except KeyError as exc:
        known = ", ".join(sorted(PROCESS_STACKS))
        raise KeyError(f"Unknown stack {name!r}; available: {known}") from exc
