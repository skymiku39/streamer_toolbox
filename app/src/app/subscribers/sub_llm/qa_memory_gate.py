from __future__ import annotations

import re

from sub_llm.ask_response import AskResponse

_LOW_VALUE_REPLY = re.compile(
    r"^(?:直播中)?(?:這段)?(?:目前)?(?:還)?沒(?:有)?提到|不知道|資料(?:中)?沒有",
    re.IGNORECASE,
)


def should_persist_qa_memory(
    response: AskResponse,
    *,
    question: str,
    published_reply: str,
    min_memory_value: int,
) -> bool:
    if not response.store_worthy:
        return False
    if response.memory_value < min_memory_value:
        return False
    if len(question.strip()) < 3:
        return False
    if not response.memory_note.strip():
        return False
    if not published_reply.strip():
        return False
    if _LOW_VALUE_REPLY.search(published_reply.strip()):
        return False
    return True
