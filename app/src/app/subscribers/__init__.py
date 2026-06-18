import importlib
import pkgutil

_SKIP_MODULES: frozenset[str] = frozenset()


def discover_subscribers() -> None:
    package = __name__
    for module_info in pkgutil.iter_modules(__path__):
        name = module_info.name
        if name.startswith("_") or name in _SKIP_MODULES:
            continue
        if module_info.ispkg:
            importlib.import_module(f"{package}.{name}.__main__")
        else:
            importlib.import_module(f"{package}.{name}")
