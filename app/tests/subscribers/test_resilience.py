from __future__ import annotations

import pytest

from sub_llm.resilience import (
    CircuitBreaker,
    LlmApiError,
    RetryPolicy,
    call_with_retry,
)


def test_llm_api_error_retryable_classification() -> None:
    assert LlmApiError("rate", status_code=429).retryable
    assert LlmApiError("server", status_code=503).retryable
    assert LlmApiError("network", status_code=None).retryable
    assert not LlmApiError("bad request", status_code=400).retryable
    assert not LlmApiError("unauthorized", status_code=401).retryable


def test_call_with_retry_succeeds_after_transient_failures() -> None:
    attempts = {"n": 0}

    def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise LlmApiError("temporary", status_code=503)
        return "ok"

    slept: list[float] = []
    result = call_with_retry(
        flaky,
        policy=RetryPolicy(max_attempts=3, base_delay_sec=0.0, max_delay_sec=0.0),
        sleep=slept.append,
    )

    assert result == "ok"
    assert attempts["n"] == 3
    assert len(slept) == 2


def test_call_with_retry_stops_immediately_on_non_retryable() -> None:
    attempts = {"n": 0}

    def boom() -> str:
        attempts["n"] += 1
        raise LlmApiError("bad", status_code=400)

    with pytest.raises(LlmApiError):
        call_with_retry(
            boom,
            policy=RetryPolicy(max_attempts=3, base_delay_sec=0.0),
            sleep=lambda _delay: None,
        )

    assert attempts["n"] == 1


def test_call_with_retry_raises_after_max_attempts() -> None:
    attempts = {"n": 0}

    def boom() -> str:
        attempts["n"] += 1
        raise LlmApiError("server", status_code=500)

    with pytest.raises(LlmApiError):
        call_with_retry(
            boom,
            policy=RetryPolicy(max_attempts=2, base_delay_sec=0.0),
            sleep=lambda _delay: None,
        )

    assert attempts["n"] == 2


def test_circuit_breaker_opens_after_threshold_and_resets() -> None:
    clock = {"t": 0.0}
    breaker = CircuitBreaker(
        failure_threshold=2,
        reset_timeout_sec=10.0,
        now=lambda: clock["t"],
    )

    assert breaker.allow()
    breaker.record_failure()
    assert breaker.allow()
    breaker.record_failure()
    assert not breaker.allow()

    clock["t"] = 9.0
    assert not breaker.allow()
    clock["t"] = 10.0
    assert breaker.allow()


def test_circuit_breaker_success_resets_failures() -> None:
    breaker = CircuitBreaker(failure_threshold=2, reset_timeout_sec=10.0)
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    assert breaker.allow()
