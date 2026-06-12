import importlib
import pkgutil


def discover_subscribers() -> None:
    package = __name__
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.ispkg or module_info.name.startswith("_"):
            continue
        importlib.import_module(f"{package}.{module_info.name}")
