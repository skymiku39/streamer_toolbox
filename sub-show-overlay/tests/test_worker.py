import time
from pathlib import Path

from sub_show_overlay.queue import OverlayMessageQueue
from sub_show_overlay.settings import LayoutMode, OverlaySettings
from sub_show_overlay.worker import OverlayRenderWorker


def _sample_payload(message_id: str) -> dict:
    return {
        "schema_version": 1,
        "topic": "chat.message",
        "platform": "twitch",
        "message_id": message_id,
        "author_name": "Viewer",
        "content": f"msg-{message_id}",
        "timestamp": "2026-06-12T17:00:00+08:00",
        "badges": [],
        "emote_url_map": {},
        "raw": {},
    }


def test_worker_updates_both_layout_ipc_files(tmp_path: Path) -> None:
    settings = OverlaySettings(
        layout=LayoutMode.BOTH,
        chat_ipc_path=tmp_path / "chat.json",
        free_ipc_path=tmp_path / "free.json",
        http_port=8765,
        http_host="127.0.0.1",
        max_lines=20,
        queue_size=20,
    )
    message_queue = OverlayMessageQueue(maxsize=20)
    worker = OverlayRenderWorker(settings, message_queue)
    worker.start()

    message_queue.put(_sample_payload("a"))
    deadline = time.time() + 2
    while worker.processed_count < 1 and time.time() < deadline:
        time.sleep(0.05)

    worker.stop()
    assert worker.processed_count == 1
    assert (tmp_path / "chat.json").exists()
    assert (tmp_path / "free.json").exists()
