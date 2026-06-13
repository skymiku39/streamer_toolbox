from __future__ import annotations

from sub_llm.prompts import resolve_system_prompt


def build_ask_messages(
    question: str,
    *,
    context: str,
    knowledge: str = "",
    system_prompt: str | None = None,
) -> list[dict[str, str]]:
    """組裝送給 LLM 的 messages（與 OpenAiCompatibleLlmClient.ask 相同）。"""
    resolved_system = (
        resolve_system_prompt() if system_prompt is None else system_prompt.strip()
    )
    messages: list[dict[str, str]] = []
    if resolved_system:
        messages.append({"role": "system", "content": resolved_system})
    user_sections: list[str] = []
    if context.strip():
        user_sections.append(f"近期直播上下文：\n{context.strip()}")
    if knowledge.strip():
        user_sections.append(f"知識庫參考：\n{knowledge.strip()}")
    user_sections.append(f"觀眾問題：{question.strip()}")
    messages.append({"role": "user", "content": "\n\n".join(user_sections)})
    return messages


def analyze_prompt_payload(
    question: str,
    *,
    context: str,
    knowledge: str = "",
    system_prompt: str | None = None,
) -> dict:
    """剖析 prompt 各區塊是否含預期記憶標記。"""
    messages = build_ask_messages(
        question,
        context=context,
        knowledge=knowledge,
        system_prompt=system_prompt,
    )
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    system_content = next(
        (m["content"] for m in messages if m["role"] == "system"),
        "",
    )
    knowledge_body = ""
    if "知識庫參考：" in user_content:
        knowledge_body = user_content.split("知識庫參考：", 1)[1].split("\n\n觀眾問題：", 1)[0].strip()
    context_body = ""
    if "近期直播上下文：" in user_content:
        context_body = user_content.split("近期直播上下文：", 1)[1].split("\n\n知識庫參考：", 1)[0]
        if "\n\n觀眾問題：" in context_body:
            context_body = context_body.split("\n\n觀眾問題：", 1)[0]
        context_body = context_body.strip()

    return {
        "system_len": len(system_content),
        "context_len": len(context_body),
        "knowledge_len": len(knowledge_body),
        "user_len": len(user_content),
        "has_stt_marker": "【直播逐字稿" in context_body,
        "has_chat_marker": "【近期聊天室" in context_body,
        "has_static_kb_marker": "【實況主知識庫】" in knowledge_body,
        "has_memory_marker": "【近期直播摘要】" in knowledge_body,
        "has_general_knowledge_hint": "本身的常識" in system_content,
        "messages": messages,
    }
