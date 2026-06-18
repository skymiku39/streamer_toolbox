from __future__ import annotations



from app.subscribers.qa_memory_mode import structured_ask_enabled

from sub_llm.ask_response import structured_output_guidance

from sub_llm.config import resolve_reply_max_length

from sub_llm.prompt_format import (

    LIVE_HEADER,

    QUESTION_HEADER,

    REF_HEADER,

    build_user_prompt,

    extract_block,

    join_groups,

)

from sub_llm.prompts import resolve_system_prompt

from sub_llm.session_recap import SESSION_RECAP_SYSTEM_GUIDANCE





def answer_guidance() -> str:

    return (

        "【回答】直接答觀眾問題。"

        "可信度：逐字稿／聊天原文＞事實＞決策＞進度／梗＞討論＞八卦；衝突時取高者。"

        "標〔八卦〕〔討論〕的記憶與既往 Bot 答覆僅供語氣參考、非事實，"

        "不可單獨拿來下肯定句。"

    )





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

    system_parts = [resolved_system, answer_guidance()]

    if structured_ask_enabled():

        system_parts.append(structured_output_guidance(limit))

    if session_recap_reference.strip():

        system_parts.append(SESSION_RECAP_SYSTEM_GUIDANCE)



    messages: list[dict[str, str]] = [

        {"role": "system", "content": join_groups(*system_parts)},

        {

            "role": "user",

            "content": build_user_prompt(

                question,

                context=context,

                knowledge=knowledge,

                game_reference=game_reference,

                session_recap_reference=session_recap_reference,

            ),

        },

    ]

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

    context_body = extract_block(user_content, LIVE_HEADER)

    reference_body = extract_block(user_content, REF_HEADER)



    return {

        "system_len": len(system_content),

        "context_len": len(context_body),

        "knowledge_len": len(reference_body),

        "game_reference_len": len(reference_body) if "遊戲:" in reference_body else 0,

        "session_recap_len": len(reference_body) if "回顧" in reference_body else 0,

        "user_len": len(user_content),

        "has_stt_marker": "逐字稿:" in context_body,

        "has_chat_marker": "聊天:" in context_body,

        "has_stream_metadata_marker": "狀態:" in context_body,

        "has_static_kb_marker": "知識:" in reference_body,

        "has_memory_marker": "記憶:" in reference_body or "Bot記憶:" in reference_body,

        "has_game_reference_marker": "遊戲:" in reference_body,

        "has_session_recap_marker": "回顧" in reference_body,

        "has_general_knowledge_hint": "通識" in system_content,

        "messages": messages,

    }

