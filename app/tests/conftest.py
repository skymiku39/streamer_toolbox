from app.module_paths import ensure_legacy_module_paths

ensure_legacy_module_paths()

from app.publishers import discover_publishers
from app.subscribers import discover_subscribers

discover_publishers()
discover_subscribers()
