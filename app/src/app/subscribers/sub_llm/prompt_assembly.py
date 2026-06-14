from __future__ import annotations

from sub_llm.ask_response import structured_output_guidance
from sub_llm.chat_format import reply_length_guidance
from sub_llm.config import resolve_reply_max_length
from sub_llm.qa_memory_mode import structured_ask_enabled
from sub_llm.prompts import resolve_system_prompt


def _answer_guidance(reply_max_length: int | None = None) -> str:
    limit = (
        reply_max_length
        if reply_max_length is not None
        else resolve_reply_max_length()
    )
    return (
        "【回答方式】直接回答觀眾問題，語氣自然，全文繁體中文（台灣），禁止簡體字。"
        + reply_length_guidance(limit)
        + "上下文沒提到的，最多一句帶過，仍須用知識庫、遊戲資料、網路搜尋或通識補足；"
        "勿反覆「直播中…」，勿只說沒提到就結束。"
        "知識庫摘要若記載你過去曾回「沒提到」，那是歷史紀錄，不代表這次也要這樣答。"
    )


def build_ask_messages(
    question: str,
    *,
    context: str,
    knowledge: str = "",
    game_reference: str = "",
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
        user_sections.append(f"近期直播上下文：\n{context.strip()}")
    if knowledge.strip():
        user_sections.append(f"知識庫參考：\n{knowledge.strip()}")
    if game_reference.strip():
        user_sections.append(f"遊戲資料參考：\n{game_reference.strip()}")
    user_sections.append(_answer_guidance(limit))
    if structured_ask_enabled():
        user_sections.append(structured_output_guidance(limit))
    user_sections.append(f"觀眾問題：{question.strip()}")
    messages.append({"role": "user", "content": "\n\n".join(user_sections)})
    return messages


def analyze_prompt_payload(
    question: str,
    *,
    context: str,
    knowledge: str = "",
    game_reference: str = "",
    system_prompt: str | None = None,
) -> dict:
    """剖析 prompt 各區塊是否含預期記憶標記。"""
    messages = build_ask_messages(
        question,
        context=context,
        knowledge=knowledge,
        game_reference=game_reference,
        system_prompt=system_prompt,
    )
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    system_content = next(
        (m["content"] for m in messages if m["role"] == "system"),
        "",
    )
    knowledge_body = ""
    if "知識庫參考：" in user_content:
        knowledge_body = user_content.split("知識庫參考：", 1)[1].split("\n\n遊戲資料參考：", 1)[0]
        if "\n\n觀眾問題：" in knowledge_body:
            knowledge_body = knowledge_body.split("\n\n觀眾問題：", 1)[0]
        knowledge_body = knowledge_body.strip()
    game_body = ""
    if "遊戲資料參考：" in user_content:
        game_body = user_content.split("遊戲資料參考：", 1)[1].split("\n\n觀眾問題：", 1)[0].strip()
    context_body = ""
    if "近期直播上下文：" in user_content:
        context_body = user_content.split("近期直播上下文：", 1)[1].split("\n\n知識庫參考：", 1)[0]
        if "\n\n遊戲資料參考：" in context_body:
            context_body = context_body.split("\n\n遊戲資料參考：", 1)[0]
        if "\n\n觀眾問題：" in context_body:
            context_body = context_body.split("\n\n觀眾問題：", 1)[0]
        context_body = context_body.strip()

    return {
        "system_len": len(system_content),
        "context_len": len(context_body),
        "knowledge_len": len(knowledge_body),
        "game_reference_len": len(game_body),
        "user_len": len(user_content),
        "has_stt_marker": "【直播逐字稿" in context_body,
        "has_chat_marker": "【近期聊天室" in context_body,
        "has_stream_metadata_marker": "【直播狀態" in context_body,
        "has_static_kb_marker": "【實況主知識庫】" in knowledge_body,
        "has_memory_marker": "【近期直播摘要】" in knowledge_body,
        "has_game_reference_marker": "【遊戲資料參考：" in game_body,
        "has_general_knowledge_hint": "通識" in system_content,
        "messages": messages,
    }
