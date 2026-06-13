"""Resolve Python executable and environment for runner subprocesses."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from app.console_encoding import utf8_subprocess_env
from app.module_paths import APP_ROOT, legacy_pythonpath_env


def subprocess_python_executable() -> str:
    """Return interpreter for ``Popen([exe, '-m', module])``.

    Under ``uv run``, ``sys.executable`` may point at ``.venv/Scripts/python.exe``
    which re-execs ``sys._base_executable`` for every ``-m`` launch, leaving two
    live processes per module (duplicate MQ consumers).
    """
    base = getattr(sys, "_base_executable", None)
    if base and os.path.isfile(base):
        if os.path.normcase(os.path.abspath(base)) != os.path.normcase(
            os.path.abspath(sys.executable)
        ):
            return base
    return sys.executable


def _venv_python_paths(venv_root: Path) -> list[str]:
    paths: list[str] = []
    site_packages = venv_root / "Lib" / "site-packages"
    if site_packages.is_dir():
        paths.append(str(site_packages))
        for pth_file in site_packages.glob("*.pth"):
            for raw_line in pth_file.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or line.startswith("import "):
                    continue
                paths.append(line)
    return paths


def subprocess_python_env() -> dict[str, str]:
    """Environment for runner child processes (venv deps + editable app layout)."""
    env = utf8_subprocess_env(legacy_pythonpath_env())

    python_paths: list[str] = []
    virtual_env = os.environ.get("VIRTUAL_ENV", "").strip()
    if virtual_env:
        python_paths.extend(_venv_python_paths(Path(virtual_env)))
        env["VIRTUAL_ENV"] = virtual_env
        scripts = Path(virtual_env) / "Scripts"
        if scripts.is_dir():
            env["PATH"] = f"{scripts}{os.pathsep}{env.get('PATH', '')}"

    app_src = APP_ROOT.parent
    if app_src.is_dir():
        python_paths.append(str(app_src))

    legacy = env.get("PYTHONPATH", "")
    if legacy:
        python_paths.append(legacy)
    if python_paths:
        # Preserve order while dropping duplicates.
        seen: set[str] = set()
        ordered: list[str] = []
        for entry in python_paths:
            key = os.path.normcase(os.path.abspath(entry))
            if key in seen:
                continue
            seen.add(key)
            ordered.append(entry)
        env["PYTHONPATH"] = os.pathsep.join(ordered)
    return env


def uses_base_python_executable() -> bool:
    return subprocess_python_executable() != sys.executable
