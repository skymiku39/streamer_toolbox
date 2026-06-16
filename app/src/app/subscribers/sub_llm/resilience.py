from __future__ import annotations

import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

# 429（限流）與 5xx（伺服器端暫時性錯誤）視為可重試；4xx（請求本身有誤）不重試。
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class LlmApiError(RuntimeError):
    """LLM API 呼叫失敗。`status_code` 為 None 代表網路層錯誤（連線／逾時）。"""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code

    @property
    def retryable(self) -> bool:
        # 網路層錯誤（status_code is None）多為暫時性，連同 429/5xx 一併重試。
        if self.status_code is None:
            return True
        return self.status_code in RETRYABLE_STATUS


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_sec: float = 0.5
    max_delay_sec: float = 8.0

    @classmethod
    def from_env(cls) -> RetryPolicy:
        return cls(
            max_attempts=max(1, _env_int("LLM_RETRY_MAX_ATTEMPTS", 3)),
            base_delay_sec=max(0.0, _env_float("LLM_RETRY_BASE_DELAY_SEC", 0.5)),
            max_delay_sec=max(0.0, _env_float("LLM_RETRY_MAX_DELAY_SEC", 8.0)),
        )

    def backoff_delay(self, attempt: int) -> float:
        """第 attempt 次（1-based）失敗後的退避秒數，含等量抖動避免同步重試。"""
        exponential = self.base_delay_sec * (2 ** (attempt - 1))
        capped = min(self.max_delay_sec, exponential)
        return capped + random.uniform(0.0, self.base_delay_sec)


def call_with_retry(
    func: Callable[[], T],
    *,
    policy: RetryPolicy,
    sleep: Callable[[float], None] = time.sleep,
    on_retry: Callable[[int, LlmApiError, float], None] | None = None,
) -> T:
    """執行 func，對可重試的 LlmApiError 做指數退避重試。"""
    last_error: LlmApiError | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return func()
        except LlmApiError as exc:
            last_error = exc
            if not exc.retryable or attempt >= policy.max_attempts:
                raise
            delay = policy.backoff_delay(attempt)
            if on_retry is not None:
                on_retry(attempt, exc, delay)
            sleep(delay)
    assert last_error is not None
    raise last_error


class CircuitBreaker:
    """連續失敗達門檻後開啟，於冷卻時間內直接拒絕呼叫，避免持續打爆故障端點。"""

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        reset_timeout_sec: float = 30.0,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._failure_threshold = max(1, failure_threshold)
        self._reset_timeout_sec = max(0.0, reset_timeout_sec)
        self._now = now
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    @classmethod
    def from_env(cls, *, now: Callable[[], float] = time.monotonic) -> CircuitBreaker:
        return cls(
            failure_threshold=max(1, _env_int("LLM_CIRCUIT_FAILURE_THRESHOLD", 5)),
            reset_timeout_sec=max(0.0, _env_float("LLM_CIRCUIT_RESET_SEC", 30.0)),
            now=now,
        )

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        return (self._now() - self._opened_at) < self._reset_timeout_sec

    def allow(self) -> bool:
        """是否允許呼叫；冷卻結束後放行一次（half-open）以探測復原。"""
        return not self.is_open

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_threshold:
            self._opened_at = self._now()
