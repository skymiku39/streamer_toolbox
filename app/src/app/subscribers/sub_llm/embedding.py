"""Chroma embedding function 解析。

預設沿用 Chroma 內建 embedding（all-MiniLM-L6-v2，英文偏向）以保持向後相容。
可改用多語系 embedding 提升繁體中文直播口語、梗與遊戲名的語意召回：

- ``LLM_EMBEDDING_BACKEND=gemini``：用既有 Gemini 金鑰呼叫 text-embedding-004
  （多語系佳、安裝輕量；每次查詢／索引需網路，離線不可用）。
- ``LLM_EMBEDDING_BACKEND=sentence-transformers`` 或僅設 ``LLM_EMBEDDING_MODEL``：
  本地 SentenceTransformer 模型（離線、無 API 成本，但需 sentence-transformers/torch）。

注意：切換 embedding 後既有向量空間不相容，需刪除 data/chroma 重新索引。
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_ENV = "LLM_EMBEDDING_MODEL"
EMBEDDING_BACKEND_ENV = "LLM_EMBEDDING_BACKEND"

DEFAULT_GEMINI_EMBEDDING_MODEL = "text-embedding-004"
_GEMINI_EMBED_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta"
_GEMINI_BATCH_SIZE = 100

_SENTENCE_TRANSFORMERS_BACKENDS = frozenset(
    {"sentence-transformers", "sentence_transformers", "st", "local"}
)


def resolve_embedding_function() -> Any | None:
    """依環境變數建立 Chroma embedding function。

    回傳 None 時呼叫端沿用 Chroma 預設 embedding。任何建立失敗（缺套件、
    缺金鑰）都記錄警告並回退預設，避免阻斷啟動。
    """
    backend = (os.environ.get(EMBEDDING_BACKEND_ENV) or "").strip().lower()
    model = (os.environ.get(EMBEDDING_MODEL_ENV) or "").strip()

    if backend == "gemini":
        return _build_gemini_embedding_function(model or DEFAULT_GEMINI_EMBEDDING_MODEL)
    if backend in _SENTENCE_TRANSFORMERS_BACKENDS:
        return _build_sentence_transformer(model)
    # 未指定 backend 時維持舊行為：只要設了模型名就走 SentenceTransformer。
    if model:
        return _build_sentence_transformer(model)
    return None


def _build_sentence_transformer(model: str) -> Any | None:
    if not model:
        logger.warning(
            "LLM_EMBEDDING_BACKEND=sentence-transformers 需同時設定 LLM_EMBEDDING_MODEL；改用預設"
        )
        return None
    try:
        from chromadb.utils import embedding_functions

        return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model)
    except Exception as exc:
        logger.warning(
            "建立 SentenceTransformer embedding 失敗（model=%s），改用 Chroma 預設: %s",
            model,
            exc,
        )
        return None


def _build_gemini_embedding_function(model: str) -> Any | None:
    from app.llm_tiers import resolve_gemini_api_key

    api_key = resolve_gemini_api_key()
    if not api_key:
        logger.warning(
            "LLM_EMBEDDING_BACKEND=gemini 需要 GOOGLE_AI_API_KEY（或 LLM_API_KEY）；改用 Chroma 預設"
        )
        return None
    try:
        return GeminiEmbeddingFunction(api_key=api_key, model=model)
    except Exception as exc:
        logger.warning(
            "建立 Gemini embedding 失敗（model=%s），改用 Chroma 預設: %s", model, exc
        )
        return None


class GeminiEmbeddingFunction:
    """以 Gemini text-embedding-* 提供多語系向量的 Chroma embedding function。"""

    def __init__(self, *, api_key: str, model: str, timeout_sec: float = 30.0) -> None:
        if not api_key:
            raise ValueError("Gemini embedding 需要 api_key")
        self._api_key = api_key
        self._model = model if model.startswith("models/") else f"models/{model}"
        self._timeout_sec = timeout_sec

    def name(self) -> str:
        # 供 Chroma 在持久化 collection 時標示 embedding 來源。
        return f"gemini:{self._model}"

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002 (Chroma 介面要求名為 input)
        texts = [str(text) for text in input]
        if not texts:
            return []
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), _GEMINI_BATCH_SIZE):
            embeddings.extend(self._embed_batch(texts[start : start + _GEMINI_BATCH_SIZE]))
        return embeddings

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        payload = {
            "requests": [
                {"model": self._model, "content": {"parts": [{"text": text}]}}
                for text in texts
            ]
        }
        url = f"{_GEMINI_EMBED_ENDPOINT}/{self._model}:batchEmbedContents"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-goog-api-key": self._api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_sec) as response:
                raw = response.read().decode("utf-8")
        except (urllib.error.URLError, OSError) as exc:
            raise RuntimeError(f"Gemini embedding 請求失敗: {exc}") from exc

        data = json.loads(raw) if raw else {}
        rows = data.get("embeddings") or []
        if len(rows) != len(texts):
            raise RuntimeError(
                f"Gemini embedding 回傳數量不符：expected {len(texts)}, got {len(rows)}"
            )
        return [[float(value) for value in (row.get("values") or [])] for row in rows]
