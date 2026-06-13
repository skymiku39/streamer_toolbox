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
