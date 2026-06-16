"""全專案系統性稽核：架構、契約、靜態分析、測試與營運就緒。

統一入口，補上 pub-sub-writing.md（逐模組）與 solid.md（設計準則）之外的整體健康度。
詳見 docs/checklists/project-audit.md。

用法：
    uv run python scripts/audit_project.py            # 本機完整（含 ruff/pytest/.env/RabbitMQ）
    uv run python scripts/audit_project.py --ci       # CI 模式（僅靜態／契約檢查）
    uv run python scripts/audit_project.py --smoke-dedup
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
AUDIT_DOC = "docs/checklists/project-audit.md"
SPEEDTABLE_DOC = ROOT / "docs" / "checklists" / "pub-sub-writing.md"
TOPICS_FILE = ROOT / "packages" / "events" / "src" / "events" / "topics.py"
EVENTS_INIT = ROOT / "packages" / "events" / "src" / "events" / "__init__.py"
MONOREPO_RULE = ".cursor/rules/monorepo-architecture.mdc"

REQUIRED_CONTROL_MODULES = ("rule-bot", "llm-bot", "show-overlay", "visual-egress")
REQUIRED_EVENTS_EXPORTS = (
    "ConfigChangedEvent",
    "TOPIC_CONFIG_CHANGED",
    "TOPIC_CONTROL_PROFILE_SWITCH",
    "TOPIC_OVERLAY_UPDATE",
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    hint: str = ""


# --- 架構：單向依賴 -------------------------------------------------------

_APP_IMPORT_RE = re.compile(r"^\s*(?:from\s+app(?:\.|\s)|import\s+app(?:\.|\s|$))")


def check_packages_no_app_import(root: Path = ROOT) -> CheckResult:
    offenders: list[str] = []
    for path in sorted((root / "packages").glob("*/src/**/*.py")):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _APP_IMPORT_RE.match(line):
                offenders.append(f"{path.relative_to(root).as_posix()}:{lineno}")
    ok = not offenders
    if ok:
        detail = "packages/ 未匯入 app/"
        hint = ""
    else:
        detail = f"違規 {len(offenders)} 處：{', '.join(offenders[:5])}"
        hint = f"packages/ 為基礎設施層，禁止依賴 app/（見 {MONOREPO_RULE}）"
    return CheckResult("packages_no_app_import", ok, detail, hint)


# --- 測試：testpaths 完整性 ----------------------------------------------


def root_testpaths(root: Path = ROOT) -> set[str]:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    paths = data["tool"]["pytest"]["ini_options"]["testpaths"]
    return {str(p).rstrip("/") for p in paths}


def check_testpaths_complete(root: Path = ROOT) -> CheckResult:
    configured = root_testpaths(root)
    missing: list[str] = []
    for tests_dir in sorted((root / "packages").glob("*/tests")):
        if not tests_dir.is_dir():
            continue
        rel = tests_dir.relative_to(root).as_posix()
        if rel not in configured:
            missing.append(rel)
    ok = not missing
    if ok:
        detail = "所有 package 測試目錄皆已納入 testpaths"
        hint = ""
    else:
        detail = f"未納入 testpaths：{', '.join(missing)}"
        hint = "請在根 pyproject.toml [tool.pytest.ini_options].testpaths 補上"
    return CheckResult("testpaths_complete", ok, detail, hint)


# --- 契約：topic 字面量集中化 --------------------------------------------


def topic_values(topics_file: Path = TOPICS_FILE) -> set[str]:
    text = topics_file.read_text(encoding="utf-8")
    values: set[str] = set()
    for match in re.finditer(r'^TOPIC_\w+\s*=\s*"([^"]+)"', text, re.MULTILINE):
        value = match.group(1)
        if value.endswith("."):  # prefix topic（如 eventsub.）以前綴比對，不掃描字面量
            continue
        values.add(value)
    return values


def topic_literal_pattern(topics: set[str]) -> re.Pattern[str] | None:
    if not topics:
        return None
    alternation = "|".join(re.escape(t) for t in sorted(topics))
    return re.compile(rf"(['\"])(?:{alternation})\1")


def check_topic_magic_strings(root: Path = ROOT) -> CheckResult:
    pattern = topic_literal_pattern(topic_values())
    offenders: list[str] = []
    if pattern is not None:
        for path in sorted((root / "app" / "src").glob("**/*.py")):
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(root).as_posix()}:{lineno}")
    ok = not offenders
    if ok:
        detail = "app/ 未發現 topic 字面量"
        hint = ""
    else:
        detail = f"topic 字面量 {len(offenders)} 處：{', '.join(offenders[:5])}"
        hint = "請改用 events.topics 的 TOPIC_* 常數，勿在 app/ 寫死 topic 字串"
    return CheckResult("topic_magic_strings", ok, detail, hint)


# --- 契約：control-plane events 已匯出 -----------------------------------


def check_events_exports(events_init: Path = EVENTS_INIT) -> CheckResult:
    text = events_init.read_text(encoding="utf-8")
    missing = [name for name in REQUIRED_EVENTS_EXPORTS if f'"{name}"' not in text]
    ok = not missing
    if ok:
        detail = "control-plane events 皆已匯出"
        hint = ""
    else:
        detail = f"events.__init__ 缺少匯出：{', '.join(missing)}"
        hint = "請在 packages/events/src/events/__init__.py 的 __all__ 補上"
    return CheckResult("events_exports", ok, detail, hint)


# --- 契約：控制面 builtin registry ---------------------------------------


def check_control_builtins() -> CheckResult:
    try:
        from control import all_descriptors  # import 時自動 register_builtins
    except Exception as exc:  # noqa: BLE001 - 回報任何匯入失敗
        return CheckResult(
            "control_builtins",
            False,
            f"匯入 control 失敗：{exc}",
            "請確認 packages/control 可正常匯入",
        )
    found = {descriptor.module_id for descriptor in all_descriptors()}
    missing = [module_id for module_id in REQUIRED_CONTROL_MODULES if module_id not in found]
    ok = not missing
    if ok:
        detail = "控制面 builtin 完整：" + ", ".join(REQUIRED_CONTROL_MODULES)
        hint = ""
    else:
        detail = f"缺少 builtin：{', '.join(missing)}"
        hint = "請確認 control.builtins.register_builtins 註冊所有內建模組"
    return CheckResult("control_builtins", ok, detail, hint)


# --- 架構：程序註冊 vs 文件漂移 ------------------------------------------


def parse_main_list_processes(text: str) -> set[str]:
    names: set[str] = set()
    for line in text.splitlines():
        match = re.match(r"^\s{2,}([a-z][a-z0-9-]+)\b", line)
        if match:
            names.add(match.group(1))
    return names


def parse_documented_processes(markdown: str) -> set[str]:
    names: set[str] = set()
    for line in markdown.splitlines():
        match = re.match(r"^\|\s*`([^`]+)`", line)
        if match:
            names.add(match.group(1).strip())
    return names


def check_registry_drift(root: Path = ROOT) -> CheckResult:
    result = subprocess.run(
        ["uv", "run", "python", "-m", "app.main", "list"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        tail = "\n".join((result.stdout + result.stderr).strip().splitlines()[-3:])
        return CheckResult(
            "registry_drift",
            False,
            tail or "app.main list 執行失敗",
            "請確認 app.main 可正常列出已註冊程序",
        )
    registered = parse_main_list_processes(result.stdout)
    documented = parse_documented_processes(SPEEDTABLE_DOC.read_text(encoding="utf-8"))
    undocumented = sorted(registered - documented)
    ok = not undocumented
    if ok:
        detail = f"{len(registered)} 個已註冊程序皆有文件"
        hint = ""
    else:
        detail = f"已註冊但未列入文件：{', '.join(undocumented)}"
        hint = "請在 docs/checklists/pub-sub-writing.md 速查總表補上對應列"
    return CheckResult("registry_drift", ok, detail, hint)


# --- 靜態分析與測試（subprocess） ----------------------------------------


def _run_tool(name: str, args: list[str], hint: str, root: Path) -> CheckResult:
    result = subprocess.run(
        args,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = (result.stdout + result.stderr).strip()
    tail = "\n".join(output.splitlines()[-5:]) if output else "(無輸出)"
    if result.returncode == 0:
        return CheckResult(name, True, tail)
    return CheckResult(name, False, tail, hint)


def run_ruff(root: Path = ROOT) -> CheckResult:
    return _run_tool(
        "ruff",
        ["uv", "run", "ruff", "check", "."],
        "請執行 uv run ruff check . 並修正",
        root,
    )


def run_pytest(root: Path = ROOT) -> CheckResult:
    return _run_tool(
        "pytest",
        ["uv", "run", "pytest", "-q"],
        "請修正失敗測試；開發者見 docs/development.md",
        root,
    )


# --- 營運就緒（重用 verify_setup） ---------------------------------------


def load_verify_setup(root: Path = ROOT) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "verify_setup",
        root / "scripts" / "verify_setup.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_setup"] = module
    spec.loader.exec_module(module)
    return module


# --- 編排 ----------------------------------------------------------------


def run_checks(
    *,
    root: Path = ROOT,
    ci: bool = False,
    smoke_dedup: bool = False,
) -> list[CheckResult]:
    checks = [
        check_packages_no_app_import(root),
        check_testpaths_complete(root),
        check_topic_magic_strings(root),
        check_events_exports(),
        check_control_builtins(),
        check_registry_drift(root),
    ]
    if not ci:
        checks.append(run_ruff(root))
        checks.append(run_pytest(root))
        verify = load_verify_setup(root)
        checks.append(verify.check_env_file(root))
        checks.append(verify.check_rabbitmq())
    if smoke_dedup:
        verify = load_verify_setup(root)
        checks.append(verify.run_dedup_smoke(root))
    return checks


def print_results(results: list[CheckResult]) -> int:
    failures: list[CheckResult] = []
    for result in results:
        status = "OK" if result.ok else "FAIL"
        print(f"[audit] {status} {result.name}: {result.detail}")
        if not result.ok:
            failures.append(result)
            if result.hint:
                print(f"        → {result.hint}")

    print()
    if failures:
        names = ", ".join(item.name for item in failures)
        print(f"PROJECT_AUDIT_FAIL ({len(failures)} 項：{names})")
        print(f"完整檢查說明見 {AUDIT_DOC}")
        return 1

    print("PROJECT_AUDIT_PASS")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="streamer-toolbox 全專案系統性稽核")
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI 模式：僅靜態／契約檢查（跳過 ruff/pytest/.env/RabbitMQ，由專屬 job 涵蓋）",
    )
    parser.add_argument(
        "--smoke-dedup",
        action="store_true",
        help="額外執行跨 process 去重自測（verify_dedup.py）",
    )
    args = parser.parse_args(argv)

    os.chdir(ROOT)
    results = run_checks(ci=args.ci, smoke_dedup=args.smoke_dedup)
    return print_results(results)


if __name__ == "__main__":
    raise SystemExit(main())
