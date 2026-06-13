"""讓 app/subscribers、app/publishers 內模組維持 `sub_*` / `ingress_*` import 路徑。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent


def ensure_legacy_module_paths() -> None:
    for name in ("subscribers", "publishers"):
        path = str(APP_ROOT / name)
        if path not in sys.path:
            sys.path.insert(0, path)


def legacy_pythonpath_env(env: dict[str, str] | None = None) -> dict[str, str]:
    merged = dict(env or os.environ)
    extra = os.pathsep.join(str(APP_ROOT / name) for name in ("subscribers", "publishers"))
    current = merged.get("PYTHONPATH", "")
    if current:
        merged["PYTHONPATH"] = f"{extra}{os.pathsep}{current}"
    else:
        merged["PYTHONPATH"] = extra
    return merged
