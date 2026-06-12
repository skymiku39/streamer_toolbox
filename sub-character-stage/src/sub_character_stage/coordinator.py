from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from pkg_events import CharacterAudioReadyEvent, CharacterExpressionReadyEvent

from sub_character_stage.cue import StageCue
from sub_character_stage.driver import StageDriver


@dataclass
class _PendingTurn:
    turn_id: str
    audio: CharacterAudioReadyEvent | None = None
    expression: CharacterExpressionReadyEvent | None = None
    fired: bool = False
    first_seen_at: float = field(default_factory=time.monotonic)


class TurnCoordinator:
    """Merge audio + expression events by turn_id; timeout falls back to audio-only."""

    def __init__(self, driver: StageDriver, *, merge_timeout_sec: float) -> None:
        if merge_timeout_sec <= 0:
            raise ValueError("merge_timeout_sec must be positive")
        self._driver = driver
        self._merge_timeout_sec = merge_timeout_sec
        self._pending: dict[str, _PendingTurn] = {}
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def handle_audio(self, event: CharacterAudioReadyEvent) -> None:
        self._update(turn_id=event.turn_id, audio=event)

    def handle_expression(self, event: CharacterExpressionReadyEvent) -> None:
        self._update(turn_id=event.turn_id, expression=event)

    def close(self) -> None:
        with self._lock:
            timers = list(self._timers.values())
            self._timers.clear()
            self._pending.clear()
        for timer in timers:
            timer.cancel()
        self._driver.close()

    def _update(
        self,
        *,
        turn_id: str,
        audio: CharacterAudioReadyEvent | None = None,
        expression: CharacterExpressionReadyEvent | None = None,
    ) -> None:
        with self._lock:
            pending = self._pending.setdefault(turn_id, _PendingTurn(turn_id=turn_id))
            if pending.fired:
                return
            if audio is not None:
                pending.audio = audio
            if expression is not None:
                pending.expression = expression

            if pending.audio is None:
                return

            if pending.expression is not None:
                self._cancel_timer_locked(turn_id)
                self._fire_locked(pending, expression_fallback=False)
                return

            if turn_id not in self._timers:
                timer = threading.Timer(
                    self._merge_timeout_sec,
                    self._on_timeout,
                    args=[turn_id],
                )
                self._timers[turn_id] = timer
                timer.start()

    def _on_timeout(self, turn_id: str) -> None:
        with self._lock:
            self._timers.pop(turn_id, None)
            pending = self._pending.get(turn_id)
            if pending is None or pending.fired or pending.audio is None:
                return
            if pending.expression is not None:
                self._fire_locked(pending, expression_fallback=False)
                return
            self._fire_locked(pending, expression_fallback=True)

    def _fire_locked(self, pending: _PendingTurn, *, expression_fallback: bool) -> None:
        if pending.audio is None or pending.fired:
            return
        pending.fired = True
        cue = StageCue(
            turn_id=pending.turn_id,
            audio=pending.audio,
            expression=pending.expression,
            expression_fallback=expression_fallback,
        )
        self._pending.pop(pending.turn_id, None)
        self._driver.play_turn(cue)

    def _cancel_timer_locked(self, turn_id: str) -> None:
        timer = self._timers.pop(turn_id, None)
        if timer is not None:
            timer.cancel()
