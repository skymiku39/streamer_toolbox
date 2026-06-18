from events import SOURCE_LOGIC_LLM, TOPIC_CHAT_REPLY, ChatReplyEvent

from app.subscribers.sub_stream_record.config import RecordConfig
from stream_store import StreamTextStore, resolve_session_for_channel
from sub_qa_memory_batch.writer import BatchQaMemoryWriter


def test_batch_writer_records_logic_llm_reply(tmp_path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    config = RecordConfig(db_path=str(tmp_path / "test.db"), session_id=None, record_mode="chat")
    writer = BatchQaMemoryWriter(store, config)
    payload = ChatReplyEvent(
        schema_version=1,
        topic=TOPIC_CHAT_REPLY,
        platform="twitch",
        channel="demo",
        content="簡短回覆",
        reply_to_message_id="msg-1",
        sender="bot",
        source=SOURCE_LOGIC_LLM,
        correlation_id="msg-1",
    ).to_dict()

    assert writer.handle(payload) is True
    session_id = resolve_session_for_channel(store, "demo")
    assert session_id is not None
    records = store.fetch_unsummarized_chat(session_id=session_id, channel="demo")
    assert any("[Bot Q&A]" in record.text for record in records)
