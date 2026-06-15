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
            "【系統提示】此為「當下實況」問題：僅能依【直播逐字稿】與【近期聊天室】"
            "描述主播剛才在做什麼；勿引用【近期直播摘要】中的 bot 舊回答或直播標題來推測；"
            "若逐字稿未明確說明，請如實轉述聽到的片段，勿捏造簡報、圖示等未出現在逐字稿的細節。"
        )
    return (
        "【系統提示】目前無近期直播逐字稿。"
        "若觀眾問「現在在幹嘛／發生什麼事／主播怎麼了」，"
        "勿從直播標題或知識庫歷史摘要推測當下畫面；"
        "應說明尚無近期語音捕捉，僅能依聊天室、直播狀態與通識簡答。"
    )
