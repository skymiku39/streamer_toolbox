from __future__ import annotations

from sub_live_status.handler import LiveStatusSubscriber


def test_live_status_publishes_once(monkeypatch) -> None:
    monkeypatch.delenv("LIVE_STATUS_ANNOUNCEMENT", raising=False)
    published: list[tuple[str, dict]] = []

    class FakeIdempotency:
        def claim(self, namespace: str, key: str) -> bool:
            return True

        def release(self, namespace: str, key: str) -> None:
            pass

        def close(self) -> None:
            pass

    subscriber = LiveStatusSubscriber(
        publish=lambda topic, payload: published.append((topic, payload)),
        idempotency=FakeIdempotency(),
    )
    payload = {
        "schema_version": 1,
        "topic": "stream.metadata",
        "platform": "twitch",
        "channel": "skymiku39",
        "timestamp": "2026-06-14T08:00:00+00:00",
        "snapshot_id": "snap-1",
        "is_live": True,
        "title": "測試標題",
        "game_name": "Just Chatting",
        "duration_seconds": 60,
    }

    subscriber.handle(payload)
    subscriber.handle(payload)

    assert len(published) == 1
    assert published[0][0] == "chat.reply"
    assert published[0][1]["source"] == "logic-status"
    assert "測試標題" in published[0][1]["content"]
