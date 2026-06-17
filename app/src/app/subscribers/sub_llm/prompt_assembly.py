from __future__ import annotations

from app.subscribers.qa_memory_mode import structured_ask_enabled
from sub_llm.ask_response import structured_output_guidance
from sub_llm.config import resolve_reply_max_length
from sub_llm.prompt_format import SECTION_SEP, join_sections
from sub_llm.prompts import resolve_system_prompt


def _answer_guidance(reply_max_length: int | None = None) -> str:
    del reply_max_length
    return "【回答】直接答觀眾問題；記憶與既往 Bot 答覆僅供參考，與逐字稿／聊天衝突時以後者為準。"


def build_ask_messages(
    question: str,
    *,
    context: str,
    knowledge: str = "",
    game_reference: str = "",
    session_recap_reference: str = "",
    system_prompt: str | None = None,
    reply_max_length: int | None = None,
) -> list[dict[str, str]]:
    """組裝送給 LLM 的 messages（與 OpenAiCompatibleLlmClient.ask 相同）。"""
    limit = (
        reply_max_length
        if reply_max_length is not None
        else resolve_reply_max_length()
    )
    resolved_system = (
        resolve_system_prompt(reply_max_length=limit)
        if system_prompt is None
        else system_prompt.strip()
    )
    messages: list[dict[str, str]] = []
    if resolved_system:
        messages.append({"role": "system", "content": resolved_system})
    user_sections: list[str] = []
    if context.strip():
        user_sections.append(f"直播:{context.strip()}")
    if knowledge.strip():
        user_sections.append(knowledge.strip())
    if game_reference.strip():
        user_sections.append(game_reference.strip())
    if session_recap_reference.strip():
        user_sections.append(session_recap_reference.strip())
    user_sections.append(_answer_guidance(limit))
    if structured_ask_enabled():
        user_sections.append(structured_output_guidance(limit))
    user_sections.append(f"問題:{question.strip()}")
    messages.append({"role": "user", "content": join_sections(*user_sections)})
    return messages


def analyze_prompt_payload(
    question: str,
    *,
    context: str,
    knowledge: str = "",
    game_reference: str = "",
    session_recap_reference: str = "",
    system_prompt: str | None = None,
) -> dict:
    """剖析 prompt 各區塊是否含預期記憶標記。"""
    messages = build_ask_messages(
        question,
        context=context,
        knowledge=knowledge,
        game_reference=game_reference,
        session_recap_reference=session_recap_reference,
        system_prompt=system_prompt,
    )
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    system_content = next(
        (m["content"] for m in messages if m["role"] == "system"),
        "",
    )
    knowledge_body = ""
    if "知識:" in user_content:
        knowledge_body = user_content.split("知識:", 1)[1].split(SECTION_SEP, 1)[0]
        if "問題:" in knowledge_body:
            knowledge_body = knowledge_body.split("問題:", 1)[0]
        knowledge_body = knowledge_body.strip()
    game_body = ""
    if "遊戲:" in user_content:
        game_body = user_content.split("遊戲:", 1)[1].split(SECTION_SEP, 1)[0]
        if "問題:" in game_body:
            game_body = game_body.split("問題:", 1)[0]
        game_body = game_body.strip()
    session_recap_body = ""
    if "回顧:" in user_content:
        session_recap_body = user_content.split("回顧:", 1)[1].split(SECTION_SEP, 1)[0]
        if "問題:" in session_recap_body:
            session_recap_body = session_recap_body.split("問題:", 1)[0]
        if "【回答】" in session_recap_body:
            session_recap_body = session_recap_body.split("【回答】", 1)[0]
        session_recap_body = session_recap_body.strip()
    context_body = ""
    if "直播:" in user_content:
        context_body = user_content.split("直播:", 1)[1].split(SECTION_SEP, 1)[0]
        if "知識:" in context_body:
            context_body = context_body.split("知識:", 1)[0]
        if "問題:" in context_body:
            context_body = context_body.split("問題:", 1)[0]
        context_body = context_body.strip()

    return {
        "system_len": len(system_content),
        "context_len": len(context_body),
        "knowledge_len": len(knowledge_body),
        "game_reference_len": len(game_body),
        "session_recap_len": len(session_recap_body),
        "user_len": len(user_content),
        "has_stt_marker": "逐字稿:" in context_body,
        "has_chat_marker": "聊天:" in context_body,
        "has_stream_metadata_marker": "狀態:" in context_body,
        "has_static_kb_marker": "知識:" in user_content,
        "has_memory_marker": "記憶:" in user_content,
        "has_game_reference_marker": "遊戲:" in user_content,
        "has_session_recap_marker": "回顧:" in user_content,
        "has_general_knowledge_hint": "通識" in system_content,
        "messages": messages,
    }
