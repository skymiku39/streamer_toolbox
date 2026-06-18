from sub_llm.memory_category import (
    DEFAULT_CATEGORY,
    category_label,
    effective_trust,
    is_factual,
    is_low_trust,
    normalize_category,
    trust_rank,
)


def test_normalize_category_valid() -> None:
    assert normalize_category("fact") == "fact"
    assert normalize_category(" GOSSIP ") == "gossip"


def test_normalize_category_invalid_or_empty_defaults() -> None:
    assert normalize_category("") == DEFAULT_CATEGORY
    assert normalize_category(None) == DEFAULT_CATEGORY
    assert normalize_category("unknown") == DEFAULT_CATEGORY


def test_trust_rank_order() -> None:
    assert trust_rank("fact") > trust_rank("decision")
    assert trust_rank("decision") > trust_rank("progress")
    assert trust_rank("progress") >= trust_rank("lore")
    assert trust_rank("discussion") > trust_rank("gossip")
    assert trust_rank("gossip") == 0


def test_effective_trust_source_fallback() -> None:
    # 無 category 時，chat/stt 來源回退到進度級可信度。
    assert effective_trust("", "chat") == trust_rank("progress")
    assert effective_trust(None, "stt") == trust_rank("progress")
    # qa 無 category → 預設最低可信度。
    assert effective_trust("", "qa") == trust_rank(DEFAULT_CATEGORY)


def test_is_factual_and_low_trust() -> None:
    assert is_factual("fact")
    assert is_factual("decision")
    assert not is_factual("gossip")
    assert is_low_trust("gossip")
    assert is_low_trust("discussion")
    assert not is_low_trust("fact")


def test_category_label_low_trust_marked() -> None:
    assert category_label("gossip") == "八卦"
    assert category_label("fact") == "事實"
