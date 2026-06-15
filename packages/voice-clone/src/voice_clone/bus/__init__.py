from __future__ import annotations

from collections.abc import Callable

from voice_clone.bus.local import LocalEventBus
from voice_clone.bus.protocol import EventBus

__all__ = ["EventBus", "LocalEventBus"]
