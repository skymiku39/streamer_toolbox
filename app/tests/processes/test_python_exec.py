from __future__ import annotations

import os
import sys
from pathlib import Path

from app.processes.python_exec import (
    _site_packages_dirs,
    _venv_python_paths,
    subprocess_python_env,
    subprocess_python_executable,
)


def test_subprocess_python_executable_prefers_base_when_shimmed() -> None:
    base = getattr(sys, "_base_executable", None)
    if (
        base
        and os.path.isfile(base)
        and os.path.normcase(os.path.abspath(base))
        != os.path.normcase(os.path.abspath(sys.executable))
    ):
        assert subprocess_python_executable() == base
    else:
        assert subprocess_python_executable() == sys.executable


def test_site_packages_dirs_supports_linux_layout(tmp_path: Path) -> None:
    linux_site = (
        tmp_path
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    linux_site.mkdir(parents=True)
    (linux_site / "pkg.pth").write_text(str(tmp_path / "extra"), encoding="utf-8")

    found = _site_packages_dirs(tmp_path)
    assert any(p == linux_site for p in found)


def test_subprocess_python_env_adds_linux_bin_to_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    venv_root = tmp_path / "venv"
    bin_dir = venv_root / "bin"
    site_packages = (
        venv_root
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    bin_dir.mkdir(parents=True)
    site_packages.mkdir(parents=True)
    (bin_dir / "streamlink").write_text("", encoding="utf-8")

    monkeypatch.setenv("VIRTUAL_ENV", str(venv_root))
    env = subprocess_python_env()

    assert env["VIRTUAL_ENV"] == str(venv_root)
    assert str(bin_dir) in env["PATH"]
    assert str(site_packages) in env["PYTHONPATH"]


def test_venv_python_paths_reads_pth_entries(tmp_path: Path) -> None:
    extra = tmp_path / "extra-lib"
    extra.mkdir()
    site_packages = tmp_path / "Lib" / "site-packages"
    site_packages.mkdir(parents=True)
    (site_packages / "editable.pth").write_text(str(extra), encoding="utf-8")

    paths = _venv_python_paths(tmp_path)
    assert str(site_packages) in paths
    assert str(extra) in paths
