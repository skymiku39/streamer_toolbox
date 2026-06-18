from __future__ import annotations

import io
import json
import sys
from unittest.mock import MagicMock

import pytest

from sub_llm.embedding import GeminiEmbeddingFunction, resolve_embedding_function


def test_resolve_embedding_function_default_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("LLM_EMBEDDING_BACKEND", raising=False)
    assert resolve_embedding_function() is None


def test_resolve_embedding_function_builds_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
    fake_ef = object()
    embedding_functions = MagicMock()
    embedding_functions.SentenceTransformerEmbeddingFunction.return_value = fake_ef
    utils = MagicMock()
    utils.embedding_functions = embedding_functions
    chromadb = MagicMock()
    chromadb.utils = utils
    monkeypatch.setitem(sys.modules, "chromadb", chromadb)
    monkeypatch.setitem(sys.modules, "chromadb.utils", utils)

    assert resolve_embedding_function() is fake_ef
    embedding_functions.SentenceTransformerEmbeddingFunction.assert_called_once_with(
        model_name="paraphrase-multilingual-MiniLM-L12-v2"
    )


def test_resolve_embedding_function_failure_falls_back_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_EMBEDDING_MODEL", "broken-model")
    utils = MagicMock()
    utils.embedding_functions.SentenceTransformerEmbeddingFunction.side_effect = RuntimeError(
        "download failed"
    )
    chromadb = MagicMock()
    chromadb.utils = utils
    monkeypatch.setitem(sys.modules, "chromadb", chromadb)
    monkeypatch.setitem(sys.modules, "chromadb.utils", utils)

    assert resolve_embedding_function() is None


def test_resolve_gemini_backend_without_key_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_EMBEDDING_BACKEND", "gemini")
    for name in ("LLM_API_KEY", "GOOGLE_AI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert resolve_embedding_function() is None


def test_resolve_gemini_backend_with_key_builds_function(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_EMBEDDING_BACKEND", "gemini")
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "test-key")
    monkeypatch.delenv("LLM_EMBEDDING_MODEL", raising=False)
    ef = resolve_embedding_function()
    assert isinstance(ef, GeminiEmbeddingFunction)
    assert ef.name() == "gemini:models/text-embedding-004"


def test_gemini_embedding_function_calls_batch_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class _FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._buf = io.BytesIO(json.dumps(payload).encode("utf-8"))

        def read(self) -> bytes:
            return self._buf.read()

        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    def fake_urlopen(request, timeout=None):  # type: ignore[no-untyped-def]
        captured["url"] = request.full_url
        captured["api_key"] = request.headers.get("X-goog-api-key")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse({"embeddings": [{"values": [0.1, 0.2]}, {"values": [0.3, 0.4]}]})

    monkeypatch.setattr("sub_llm.embedding.urllib.request.urlopen", fake_urlopen)

    ef = GeminiEmbeddingFunction(api_key="test-key", model="text-embedding-004")
    vectors = ef(["你好", "嗨"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert captured["url"].endswith("/models/text-embedding-004:batchEmbedContents")
    assert captured["api_key"] == "test-key"
    assert len(captured["body"]["requests"]) == 2


def test_gemini_embedding_function_rejects_count_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeResponse:
        def read(self) -> bytes:
            return json.dumps({"embeddings": [{"values": [0.1]}]}).encode("utf-8")

        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(
        "sub_llm.embedding.urllib.request.urlopen",
        lambda request, timeout=None: _FakeResponse(),
    )
    ef = GeminiEmbeddingFunction(api_key="test-key", model="text-embedding-004")
    with pytest.raises(RuntimeError):
        ef(["a", "b"])
