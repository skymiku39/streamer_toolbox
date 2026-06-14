from events import TOPIC_MEMORY_QA_RECORD, MemoryQaRecordEvent


def test_memory_qa_record_round_trip() -> None:
    event = MemoryQaRecordEvent.build(
        channel="demo",
        platform="twitch",
        correlation_id="msg-1",
        question="蒜頭王八是什麼",
        reply="寶可夢諧音梗。",
        memory_note="觀眾問蒜頭王八，解釋為寶可夢諧音梗。",
        memory_value=4,
        store_worthy=True,
        ask_author="alice",
    )
    restored = MemoryQaRecordEvent.from_dict(event.to_dict())
    assert restored.topic == TOPIC_MEMORY_QA_RECORD
    assert restored.question == "蒜頭王八是什麼"
    assert restored.memory_value == 4
