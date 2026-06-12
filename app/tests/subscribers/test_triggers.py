from sub_llm.triggers import TriggerMatcher


def test_extract_question_matches_prefix() -> None:
    matcher = TriggerMatcher(("!ask",))
    assert matcher.extract_question("!ask 今天天氣如何？") == "今天天氣如何？"


def test_extract_question_case_insensitive() -> None:
    matcher = TriggerMatcher(("!Ask",))
    assert matcher.extract_question("!ASK 你好") == "你好"


def test_extract_question_ignores_non_trigger() -> None:
    matcher = TriggerMatcher(("!ask",))
    assert matcher.extract_question("hello world") is None


def test_extract_question_requires_text_after_prefix() -> None:
    matcher = TriggerMatcher(("!ask",))
    assert matcher.extract_question("!ask") is None
