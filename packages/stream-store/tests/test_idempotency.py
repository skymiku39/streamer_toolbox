from pathlib import Path

from stream_store.idempotency import IdempotencyStore


def test_claim_is_idempotent_across_same_key(tmp_path: Path) -> None:
    store = IdempotencyStore(tmp_path / "dedup.db", ttl_seconds=3600)

    assert store.claim("ingress.chat.message", "msg-1") is True
    assert store.claim("ingress.chat.message", "msg-1") is False

    store.close()


def test_claim_allows_different_keys_and_namespaces(tmp_path: Path) -> None:
    store = IdempotencyStore(tmp_path / "dedup.db")

    assert store.claim("ingress.chat.message", "msg-1") is True
    assert store.claim("ingress.chat.message", "msg-2") is True
    assert store.claim("sub_llm.chat.trigger", "msg-1") is True

    store.close()


def test_claim_with_empty_key_is_noop(tmp_path: Path) -> None:
    store = IdempotencyStore(tmp_path / "dedup.db")

    assert store.claim("ingress.chat.message", "") is True
    assert store.claim("ingress.chat.message", "") is True

    store.close()


def test_release_allows_reclaim(tmp_path: Path) -> None:
    store = IdempotencyStore(tmp_path / "dedup.db")

    assert store.claim("sub_llm.chat.trigger", "msg-1") is True
    assert store.claim("sub_llm.chat.trigger", "msg-1") is False
    store.release("sub_llm.chat.trigger", "msg-1")
    assert store.claim("sub_llm.chat.trigger", "msg-1") is True

    store.close()
