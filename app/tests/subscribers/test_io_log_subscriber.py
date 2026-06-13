from __future__ import annotations

import json
from pathlib import Path

from events import TOPIC_CHAT_MESSAGE

from sub_io_log.__main__ import IoLogSubscriber


def test_handle_writes_jsonl_and_uses_message_id_prefix(tmp_path: Path) -> None:
    log_path = tmp_path / "chat_io.jsonl"
    subscriber = IoLogSubscriber(log_path=log_path, console=False)
    subscriber.handle(
        {
            "schema_version": 1,
            "topic": TOPIC_CHAT_MESSAGE,
            "platform": "twitch",
            "message_id": "abcdefgh1234",
            "author_name": "Viewer",
            "content": "hello",
            "timestamp": "2026-06-12T17:00:00+08:00",
            "channel": "testchannel",
        }
    )

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["message_id"] == "abcdefgh1234"
    assert payload["topic"] == TOPIC_CHAT_MESSAGE
