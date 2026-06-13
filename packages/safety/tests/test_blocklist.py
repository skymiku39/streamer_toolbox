from safety import BlocklistSafetyFilter, PassThroughSafetyFilter


def test_pass_through_strips_whitespace() -> None:
    safety = PassThroughSafetyFilter()
    assert safety.filter_input("  hello  ") == "hello"
    assert safety.filter_input("   ") is None


def test_blocklist_blocks_input() -> None:
    safety = BlocklistSafetyFilter(blocklist=frozenset({"spam"}))
    assert safety.filter_input("這是 spam 訊息") is None
    assert safety.filter_input("正常訊息") == "正常訊息"


def test_blocklist_case_insensitive() -> None:
    safety = BlocklistSafetyFilter(blocklist=frozenset({"bad"}))
    assert safety.filter_output("BAD word") is None
