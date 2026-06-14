import pytest

from app.subscribers.qa_memory_mode import resolve_qa_memory_mode, structured_ask_enabled


def test_resolve_qa_memory_mode_none_by_default(monkeypatch) -> None:
    monkeypatch.delenv("QA_MEMORY_MODE", raising=False)
    monkeypatch.delenv("QA_MEMORY_BATCH_ENABLED", raising=False)
    monkeypatch.delenv("QA_MEMORY_STRUCTURED_ENABLED", raising=False)
    monkeypatch.delenv("LLM_STRUCTURED_ASK", raising=False)
    monkeypatch.delenv("LLM_QA_MEMORY_ENABLED", raising=False)
    assert resolve_qa_memory_mode() == "none"
    assert not structured_ask_enabled()


def test_resolve_qa_memory_mode_structured(monkeypatch) -> None:
    monkeypatch.setenv("QA_MEMORY_MODE", "structured")
    assert resolve_qa_memory_mode() == "structured"
    assert structured_ask_enabled()


def test_resolve_qa_memory_mode_batch(monkeypatch) -> None:
    monkeypatch.setenv("QA_MEMORY_MODE", "batch")
    assert resolve_qa_memory_mode() == "batch"
    assert not structured_ask_enabled()


def test_qa_memory_read_enabled_for_structured_and_batch(monkeypatch) -> None:
    from app.subscribers.qa_memory_mode import qa_memory_read_enabled

    monkeypatch.setenv("QA_MEMORY_MODE", "none")
    assert not qa_memory_read_enabled()
    monkeypatch.setenv("QA_MEMORY_MODE", "structured")
    assert qa_memory_read_enabled()
    monkeypatch.setenv("QA_MEMORY_MODE", "batch")
    assert qa_memory_read_enabled()


def test_resolve_qa_memory_mode_rejects_unknown(monkeypatch) -> None:
    monkeypatch.setenv("QA_MEMORY_MODE", "invalid")
    with pytest.raises(ValueError):
        resolve_qa_memory_mode()
