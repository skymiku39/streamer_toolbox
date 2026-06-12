from sub_show_overlay.queue import OverlayMessageQueue


def test_queue_drops_oldest_when_full() -> None:
    queue = OverlayMessageQueue(maxsize=2)
    queue.put({"message_id": "1"})
    queue.put({"message_id": "2"})
    queue.put({"message_id": "3"})

    stats = queue.stats()
    assert stats.received == 3
    assert stats.dropped == 1

    batch = queue.drain_batch(max_items=10, timeout=0.1)
    ids = [item["message_id"] for item in batch]
    assert ids == ["2", "3"]


def test_drain_batch_coalesces_multiple_items() -> None:
    queue = OverlayMessageQueue(maxsize=10)
    for index in range(4):
        queue.put({"message_id": str(index)})

    batch = queue.drain_batch(max_items=10, timeout=0.1)
    assert len(batch) == 4
    assert queue.stats().coalesced == 3
