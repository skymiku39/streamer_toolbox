from collections.abc import Callable, Iterable
from functools import wraps
from typing import Any, TypeVar

from app.processes.base import ProcessSpec, PublisherSpec, SubscriberSpec

F = TypeVar("F", bound=Callable[..., object])


def _runner_module(module: str) -> str:
    if module.endswith(".__main__"):
        return module.rsplit(".", 1)[0]
    return module


class ProcessRegistry:
    def __init__(self) -> None:
        self._publishers: dict[str, PublisherSpec] = {}
        self._subscribers: dict[str, SubscriberSpec] = {}

    def register_publisher(self, spec: PublisherSpec) -> None:
        if spec.name in self._publishers:
            return
        self._publishers[spec.name] = spec

    def register_subscriber(self, spec: SubscriberSpec) -> None:
        if spec.name in self._subscribers:
            return
        self._subscribers[spec.name] = spec

    def get(self, name: str) -> ProcessSpec:
        if name in self._publishers:
            return self._publishers[name]
        if name in self._subscribers:
            return self._subscribers[name]
        raise KeyError(f"Unknown process: {name}")

    def all_publishers(self) -> list[PublisherSpec]:
        return sorted(self._publishers.values(), key=lambda spec: spec.name)

    def all_subscribers(self) -> list[SubscriberSpec]:
        return sorted(self._subscribers.values(), key=lambda spec: spec.name)

    def all_processes(self) -> list[ProcessSpec]:
        return sorted(
            [*self._publishers.values(), *self._subscribers.values()],
            key=lambda spec: spec.name,
        )

    def resolve(self, names: Iterable[str]) -> list[ProcessSpec]:
        return [self.get(name) for name in names]


registry = ProcessRegistry()


def register_publisher(
    name: str,
    exchange: str,
    description: str,
) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            from app.processes.process_lock import acquire_process_lock

            with acquire_process_lock(name):
                return func(*args, **kwargs)

        registry.register_publisher(
            PublisherSpec(
                name=name,
                module=_runner_module(func.__module__),
                description=description,
                kind="publisher",
                exchange=exchange,
            )
        )
        return wrapped  # type: ignore[return-value]

    return decorator


def register_subscriber(
    name: str,
    exchange: str,
    queue: str,
    description: str,
) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            from app.processes.process_lock import acquire_process_lock

            with acquire_process_lock(name):
                return func(*args, **kwargs)

        registry.register_subscriber(
            SubscriberSpec(
                name=name,
                module=_runner_module(func.__module__),
                description=description,
                kind="subscriber",
                exchange=exchange,
                queue=queue,
            )
        )
        return wrapped  # type: ignore[return-value]

    return decorator
