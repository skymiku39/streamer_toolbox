"""命名風險稽核（Monorepo 規則五）。

掃描跨 package、app↔package 的同名公開 class／函式，降低 wrong-import 風險。
白名單與守備範圍定義於本模組；由 ``audit_project.py`` 編排進 CI。

守備範圍
--------
- **Class**：``packages/*/src`` 內 top-level ``class Name``；以及 ``app/src`` 內同名 class
  是否與 package 衝突。
- **Function**：``packages/*/src`` 內跨 package 的 top-level ``def name``（排除常見樣板函式）。

刻意平行設計須登記白名單；其餘同名符號應加領域前綴或收斂至 canonical package。
詳見 ``.cursor/rules/monorepo-architecture.mdc`` 規則五與 ``docs/development.md``。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MONOREPO_RULE = ".cursor/rules/monorepo-architecture.mdc"

_CLASS_DEF_RE = re.compile(r"^class\s+([A-Z]\w*)", re.MULTILINE)
_FUNCTION_DEF_RE = re.compile(r"^def\s+([a-z_]\w*)", re.MULTILINE)

# 跨 package 同名 public class 白名單（刻意的平行套件，如 lens 雙生）。
INTENTIONAL_PARALLEL_CLASSES: dict[str, frozenset[str]] = {
    "ChatMessage": frozenset({"ttvchat-lens", "tubechat-lens"}),
    "ChatSession": frozenset({"ttvchat-lens", "tubechat-lens"}),
    "LiveChatReader": frozenset({"ttvchat-lens", "tubechat-lens"}),
}

# app 與 package 允許同名的 class（極少數；預設為空，新增須附理由）。
INTENTIONAL_APP_PACKAGE_CLASSES: dict[str, frozenset[str]] = {}

# 跨 package 同名 public 函式白名單。
INTENTIONAL_PARALLEL_FUNCTIONS: dict[str, frozenset[str]] = {
    # ttvchat-lens ↔ tubechat-lens 平行 CLI／桌面工具
    "desktop_dir": frozenset({"ttvchat-lens", "tubechat-lens"}),
    "ensure_desktop_deps": frozenset({"ttvchat-lens", "tubechat-lens"}),
    "is_port_open": frozenset({"ttvchat-lens", "tubechat-lens"}),
    "print_message": frozenset({"ttvchat-lens", "tubechat-lens"}),
    "project_root": frozenset({"ttvchat-lens", "tubechat-lens"}),
    "run_tauri": frozenset({"ttvchat-lens", "tubechat-lens"}),
    "start_server": frozenset({"ttvchat-lens", "tubechat-lens"}),
    "stop_server": frozenset({"ttvchat-lens", "tubechat-lens"}),
    # 已知技術債：樣本前處理（voice-clone/audio）與 STT 降噪（stt-core）尚未合併
    "spectral_gate": frozenset({"stt-core", "voice-clone"}),
    "suppress_noise_for_stt": frozenset({"stt-core", "voice-clone"}),
}

# 常見樣板／生命週期函式，不納入跨 package 函式碰撞掃描。
FUNCTION_COLLISION_SKIP: frozenset[str] = frozenset(
    {
        "main",
        "build_parser",
        "from_env",
        "load",
        "validate",
        "close",
        "handle",
        "run",
        "connect",
        "subscribe",
        "publish",
        "parse_args",
        "repo_root",
        "default_config_dir",
        "ensure_layout",
        "all_descriptors",
        "discover_subscribers",
        "register_subscriber",
        "register_publisher",
        "preload_in_background",
        "wait_until_ready",
        "to_dict",
        "from_dict",
        "from_dir",
        "knowledge_file",
        "topic_values",
        "parse_stack_keys",
        "parse_main_list_processes",
        "parse_documented_processes",
        "print_results",
        "run_checks",
    }
)


@dataclass(frozen=True)
class NamingViolation:
    """單一命名碰撞項目。"""

    symbol: str
    locations: tuple[str, ...]


def _read_python(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _iter_package_sources(root: Path):
    packages_root = root / "packages"
    for path in sorted(packages_root.glob("*/src/**/*.py")):
        if "__pycache__" in path.parts:
            continue
        package = path.relative_to(packages_root).parts[0]
        yield package, path


def _iter_app_sources(root: Path):
    app_root = root / "app" / "src"
    for path in sorted(app_root.glob("**/*.py")):
        if "__pycache__" in path.parts:
            continue
        module = path.relative_to(app_root).as_posix().removesuffix(".py")
        yield module, path


def collect_package_class_defs(root: Path) -> dict[str, set[str]]:
    """{類別名: {package 目錄名}}"""
    defs: dict[str, set[str]] = {}
    for package, path in _iter_package_sources(root):
        text = _read_python(path)
        if text is None:
            continue
        for match in _CLASS_DEF_RE.finditer(text):
            defs.setdefault(match.group(1), set()).add(package)
    return defs


def collect_app_class_defs(root: Path) -> dict[str, set[str]]:
    """{類別名: {app 模組路徑}}"""
    defs: dict[str, set[str]] = {}
    for module, path in _iter_app_sources(root):
        text = _read_python(path)
        if text is None:
            continue
        for match in _CLASS_DEF_RE.finditer(text):
            defs.setdefault(match.group(1), set()).add(module)
    return defs


def collect_package_function_defs(root: Path) -> dict[str, set[str]]:
    """{函式名: {package 目錄名}}（僅 public top-level def）"""
    defs: dict[str, set[str]] = {}
    for package, path in _iter_package_sources(root):
        text = _read_python(path)
        if text is None:
            continue
        for match in _FUNCTION_DEF_RE.finditer(text):
            name = match.group(1)
            if name.startswith("_") or name in FUNCTION_COLLISION_SKIP:
                continue
            defs.setdefault(name, set()).add(package)
    return defs


def cross_package_class_violations(root: Path) -> list[NamingViolation]:
    violations: list[NamingViolation] = []
    for name, packages in sorted(collect_package_class_defs(root).items()):
        if len(packages) < 2:
            continue
        allowed = INTENTIONAL_PARALLEL_CLASSES.get(name)
        if allowed is not None and packages <= allowed:
            continue
        violations.append(
            NamingViolation(
                symbol=name,
                locations=tuple(f"pkg:{pkg}" for pkg in sorted(packages)),
            )
        )
    return violations


def app_package_class_violations(root: Path) -> list[NamingViolation]:
    pkg_defs = collect_package_class_defs(root)
    app_defs = collect_app_class_defs(root)
    violations: list[NamingViolation] = []
    for name in sorted(set(pkg_defs) & set(app_defs)):
        allowed = INTENTIONAL_APP_PACKAGE_CLASSES.get(name)
        if allowed is not None:
            continue
        locations = tuple(
            sorted(f"pkg:{pkg}" for pkg in pkg_defs[name])
            + sorted(f"app:{mod}" for mod in app_defs[name])
        )
        violations.append(NamingViolation(symbol=name, locations=locations))
    return violations


def cross_package_function_violations(root: Path) -> list[NamingViolation]:
    violations: list[NamingViolation] = []
    for name, packages in sorted(collect_package_function_defs(root).items()):
        if len(packages) < 2:
            continue
        allowed = INTENTIONAL_PARALLEL_FUNCTIONS.get(name)
        if allowed is not None and packages <= allowed:
            continue
        violations.append(
            NamingViolation(
                symbol=name,
                locations=tuple(f"pkg:{pkg}" for pkg in sorted(packages)),
            )
        )
    return violations


def _format_violations(violations: list[NamingViolation], *, limit: int = 5) -> str:
    parts = [
        f"{item.symbol}（{', '.join(item.locations)}）" for item in violations[:limit]
    ]
    return "; ".join(parts)


def check_cross_package_duplicate_class(root: Path) -> tuple[bool, str, str]:
    violations = cross_package_class_violations(root)
    if not violations:
        return True, "跨 package 無未預期的同名 public class", ""
    detail = f"同名 public class {len(violations)} 組：{_format_violations(violations)}"
    hint = (
        "跨 package 公開類別請加領域前綴以避免 import 混淆"
        f"（見 {MONOREPO_RULE}）；刻意的平行設計請加入 "
        "scripts/naming_audit.py 的 INTENTIONAL_PARALLEL_CLASSES"
    )
    return False, detail, hint


def check_app_package_duplicate_class(root: Path) -> tuple[bool, str, str]:
    violations = app_package_class_violations(root)
    if not violations:
        return True, "app 與 packages 無未預期的同名 public class", ""
    detail = f"app↔package 同名 class {len(violations)} 組：{_format_violations(violations)}"
    hint = (
        "app 與 package 的公開類別若職責不同，請加領域前綴"
        "（例：ConnectorTokenProvider vs identity_oauth.TokenProvider）；"
        "或登記 INTENTIONAL_APP_PACKAGE_CLASSES 白名單"
    )
    return False, detail, hint


def check_cross_package_duplicate_function(root: Path) -> tuple[bool, str, str]:
    violations = cross_package_function_violations(root)
    if not violations:
        return True, "跨 package 無未預期的同名 public 函式", ""
    detail = f"同名 public 函式 {len(violations)} 組：{_format_violations(violations)}"
    hint = (
        "跨 package 公開函式若語意不同請加領域前綴或收斂至 canonical package"
        f"（見 {MONOREPO_RULE}）；平行設計請加入 INTENTIONAL_PARALLEL_FUNCTIONS"
    )
    return False, detail, hint
