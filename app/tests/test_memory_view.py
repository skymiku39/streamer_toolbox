from __future__ import annotations

from pathlib import Path

from stream_store import ACTIVE_SESSION_KEY, StreamTextStore

from app.memory_view.http_server import MemoryBoardHttpServer, MemoryBoardState
from app.memory_view.service import MemoryViewService


def test_memory_view_service_lists_summaries_chronologically(tmp_path: Path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    session_id = "sess-1"
    store.save_summary(
        session_id=session_id,
        period_start="2026-06-12T10:00:00+00:00",
        period_end="2026-06-12T10:05:00+00:00",
        source="chat",
        content="first",
        record_count=1,
    )
    store.save_summary(
        session_id=session_id,
        period_start="2026-06-12T10:05:00+00:00",
        period_end="2026-06-12T10:10:00+00:00",
        source="stt",
        content="second",
        record_count=2,
    )
    service = MemoryViewService(store)
    summaries = service.list_summaries(session_id)
    assert [summary.content for summary in summaries] == ["first", "second"]
    store.close()


def test_memory_board_api(tmp_path: Path) -> None:
    store = StreamTextStore(tmp_path / "test.db")
    session_id = "sess-board"
    store.set_checkpoint(ACTIVE_SESSION_KEY, session_id)
    store.save_summary(
        session_id=session_id,
        period_start="2026-06-12T10:00:00+00:00",
        period_end="2026-06-12T10:05:00+00:00",
        source="chat",
        content="board content",
        record_count=1,
    )
    service = MemoryViewService(store)
    state = MemoryBoardState()
    server = MemoryBoardHttpServer(host="127.0.0.1", port=0, service=service, state=state)
    server.start()
    try:
        import urllib.request

        port = server._server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(f"{base}/api/sessions") as response:
            sessions_payload = json_loads(response.read())
        assert sessions_payload["active_session_id"] == session_id
        with urllib.request.urlopen(f"{base}/api/sessions/{session_id}/summaries") as response:
            summaries_payload = json_loads(response.read())
        assert summaries_payload["summaries"][0]["content"] == "board content"
    finally:
        server.stop()
        store.close()


def json_loads(raw: bytes) -> dict:
    import json

    return json.loads(raw.decode("utf-8"))
