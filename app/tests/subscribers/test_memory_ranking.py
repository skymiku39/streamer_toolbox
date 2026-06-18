from sub_llm.memory_ranking import period_end_from_snippet, rank_memory_snippets


def test_period_end_from_snippet_prefers_metadata() -> None:
    doc = "[chat] 2026-06-12T10:00:00+00:00 .. 2026-06-12T10:05:00+00:00\n內容"
    assert period_end_from_snippet(doc, {"period_end": "2026-06-12T10:30:00+00:00"}) == (
        "2026-06-12T10:30:00+00:00"
    )


def test_period_end_from_snippet_parses_document_header() -> None:
    doc = "[chat] 2026-06-12T10:00:00+00:00 .. 2026-06-12T10:05:00+00:00\n內容"
    assert period_end_from_snippet(doc, {}) == "2026-06-12T10:05:00+00:00"


def test_rank_memory_snippets_sorts_by_period_end_desc() -> None:
    older = "[chat] 2026-06-12T10:00:00+00:00 .. 2026-06-12T10:05:00+00:00\n舊摘要"
    newer = "[chat] 2026-06-12T10:30:00+00:00 .. 2026-06-12T10:35:00+00:00\n新摘要"
    ranked = rank_memory_snippets(
        [older, newer],
        [
            {"period_end": "2026-06-12T10:05:00+00:00"},
            {"period_end": "2026-06-12T10:35:00+00:00"},
        ],
    )
    assert ranked == [newer, older]


def test_rank_memory_snippets_deduplicates() -> None:
    doc = "[chat] 2026-06-12T10:00:00+00:00 .. 2026-06-12T10:05:00+00:00\n重複"
    ranked = rank_memory_snippets([doc, doc], [{}, {}])
    assert ranked == [doc]


def test_rank_memory_snippets_relevance_first_when_distances_given() -> None:
    # 提供向量相似度時改以「相關度為主」：高相關但低可信度的片段，
    # 應排在低相關但高可信度的片段之前。
    relevant_gossip = "[qa] 2026-06-12T10:00:00+00:00 .. 2026-06-12T10:00:00+00:00\n[八卦]高相關八卦"
    distant_fact = "[qa] 2026-06-12T11:00:00+00:00 .. 2026-06-12T11:00:00+00:00\n[事實]低相關事實"
    ranked = rank_memory_snippets(
        [relevant_gossip, distant_fact],
        [
            {"category": "gossip", "source": "qa", "period_end": "2026-06-12T10:00:00+00:00"},
            {"category": "fact", "source": "qa", "period_end": "2026-06-12T11:00:00+00:00"},
        ],
        [0.1, 0.85],
    )
    assert ranked == [relevant_gossip, distant_fact]


def test_rank_memory_snippets_trust_assists_on_similar_relevance() -> None:
    # 相關度相近時，可信度作為輔助：高可信度勝出。
    gossip = "[qa] 2026-06-12T10:00:00+00:00 .. 2026-06-12T10:00:00+00:00\n[八卦]八卦"
    fact = "[qa] 2026-06-12T10:00:00+00:00 .. 2026-06-12T10:00:00+00:00\n[事實]事實"
    ranked = rank_memory_snippets(
        [gossip, fact],
        [
            {"category": "gossip", "source": "qa"},
            {"category": "fact", "source": "qa"},
        ],
        [0.3, 0.3],
    )
    assert ranked == [fact, gossip]


def test_rank_memory_snippets_trust_overrides_recency() -> None:
    # 較新的八卦不應排在較舊的事實之前。
    newer_gossip = "[qa] 2026-06-12T11:00:00+00:00 .. 2026-06-12T11:00:00+00:00\n[八卦]新八卦"
    older_fact = "[qa] 2026-06-12T10:00:00+00:00 .. 2026-06-12T10:00:00+00:00\n[事實]舊事實"
    ranked = rank_memory_snippets(
        [newer_gossip, older_fact],
        [
            {"period_end": "2026-06-12T11:00:00+00:00", "category": "gossip", "source": "qa"},
            {"period_end": "2026-06-12T10:00:00+00:00", "category": "fact", "source": "qa"},
        ],
    )
    assert ranked == [older_fact, newer_gossip]
