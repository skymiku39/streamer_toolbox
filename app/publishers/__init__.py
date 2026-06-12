import importlib
import pkgutil


def discover_publishers() -> None:
    package = __name__
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.ispkg:
            importlib.import_module(f"{package}.{module_info.name}.__main__")
