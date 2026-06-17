from __future__ import annotations

import re

_CURRENT_ACTIVITY = re.compile(
    r"在幹嘛|在做什麼|在做啥|發生什麼|怎麼了|剛剛|剛才|現在.*(?:做|聊|玩|發生)",
)


def is_current_activity_question(question: str) -> bool:
    """觀眾問的是「此刻／剛才主播在做什麼」而非一般知識題。"""
    return bool(_CURRENT_ACTIVITY.search(question.strip()))


def current_activity_context_hint(*, has_stt: bool) -> str:
    if has_stt:
        return (
            "提示:當下實況題，僅依逐字稿與聊天描述主播剛才在做什麼；"
            "勿用記憶摘要或直播標題推測；逐字稿未明說則如實轉述，勿捏造細節。"
        )
    return (
        "提示:目前無近期逐字稿；若問當下在幹嘛，勿從標題或記憶推測畫面，"
        "應說明尚無語音捕捉，僅能依聊天與直播狀態簡答。"
    )
