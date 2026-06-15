from __future__ import annotations

from control.descriptor import ModuleDescriptor

_registry: dict[str, ModuleDescriptor] = {}


def register(descriptor: ModuleDescriptor) -> None:
    module_id = descriptor.module_id
    if module_id in _registry:
        raise ValueError(f"module_id already registered: {module_id!r}")
    _registry[module_id] = descriptor


def get(module_id: str) -> ModuleDescriptor | None:
    return _registry.get(module_id)


def all_descriptors() -> tuple[ModuleDescriptor, ...]:
    return tuple(_registry[k] for k in sorted(_registry))


def clear() -> None:
    _registry.clear()
