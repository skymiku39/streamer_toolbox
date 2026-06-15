from sub_llm.live_activity import (
    current_activity_context_hint,
    is_current_activity_question,
)


def test_is_current_activity_question() -> None:
    assert is_current_activity_question("主播剛剛在幹嘛？")
    assert is_current_activity_question("現在發生什麼事了")
    assert not is_current_activity_question("蒜頭王八是什麼")


def test_current_activity_hint_with_stt() -> None:
    hint = current_activity_context_hint(has_stt=True)
    assert "直播逐字稿" in hint
    assert "勿引用" in hint


def test_current_activity_hint_without_stt() -> None:
    hint = current_activity_context_hint(has_stt=False)
    assert "無近期直播逐字稿" in hint
