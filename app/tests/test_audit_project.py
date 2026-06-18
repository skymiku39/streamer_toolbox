from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "audit_project",
    _ROOT / "scripts" / "audit_project.py",
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["audit_project"] = _mod
_spec.loader.exec_module(_mod)


def test_packages_no_app_import_clean(tmp_path: Path) -> None:
    pkg = tmp_path / "packages" / "demo" / "src" / "demo"
    pkg.mkdir(parents=True)
    (pkg / "mod.py").write_text("from events import ChatMessageEvent\n", encoding="utf-8")
    result = _mod.check_packages_no_app_import(tmp_path)
    assert result.ok is True


def test_packages_no_app_import_detects_violation(tmp_path: Path) -> None:
    pkg = tmp_path / "packages" / "demo" / "src" / "demo"
    pkg.mkdir(parents=True)
    (pkg / "mod.py").write_text("from app.subscribers import thing\n", encoding="utf-8")
    result = _mod.check_packages_no_app_import(tmp_path)
    assert result.ok is False
    assert "packages/demo/src/demo/mod.py:1" in result.detail


def test_packages_no_app_import_ignores_lookalike(tmp_path: Path) -> None:
    pkg = tmp_path / "packages" / "demo" / "src" / "demo"
    pkg.mkdir(parents=True)
    (pkg / "mod.py").write_text("import application_config\n", encoding="utf-8")
    result = _mod.check_packages_no_app_import(tmp_path)
    assert result.ok is True


def _write_pkg_class(root: Path, package: str, name: str) -> None:
    pkg = root / "packages" / package / "src" / package.replace("-", "_")
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / f"{name.lower()}.py").write_text(f"class {name}:\n    pass\n", encoding="utf-8")


def test_cross_package_duplicate_class_clean(tmp_path: Path) -> None:
    _write_pkg_class(tmp_path, "alpha", "Widget")
    _write_pkg_class(tmp_path, "beta", "Gadget")
    result = _mod.check_cross_package_duplicate_class(tmp_path)
    assert result.ok is True
    assert result.name == "naming_cross_package_class"


def test_cross_package_duplicate_class_detects_collision(tmp_path: Path) -> None:
    _write_pkg_class(tmp_path, "alpha", "Worker")
    _write_pkg_class(tmp_path, "beta", "Worker")
    result = _mod.check_cross_package_duplicate_class(tmp_path)
    assert result.ok is False
    assert result.name == "naming_cross_package_class"
    assert "Worker" in result.detail


def test_app_package_duplicate_class_detects_collision(tmp_path: Path) -> None:
    _write_pkg_class(tmp_path, "alpha", "DupClass")
    app_mod = tmp_path / "app" / "src" / "app" / "demo"
    app_mod.mkdir(parents=True)
    (app_mod / "mod.py").write_text("class DupClass:\n    pass\n", encoding="utf-8")
    result = _mod.check_app_package_duplicate_class(tmp_path)
    assert result.ok is False
    assert "DupClass" in result.detail


def test_cross_package_duplicate_function_detects_collision(tmp_path: Path) -> None:
    for package in ("alpha", "beta"):
        pkg = tmp_path / "packages" / package / "src" / package
        pkg.mkdir(parents=True)
        (pkg / "fn.py").write_text("def unique_helper():\n    return 1\n", encoding="utf-8")
    result = _mod.check_cross_package_duplicate_function(tmp_path)
    assert result.ok is False
    assert "unique_helper" in result.detail


def test_app_package_duplicate_function_detects_collision(tmp_path: Path) -> None:
    pkg = tmp_path / "packages" / "alpha" / "src" / "alpha"
    pkg.mkdir(parents=True)
    (pkg / "fn.py").write_text("def shared_fn():\n    return 1\n", encoding="utf-8")
    app_mod = tmp_path / "app" / "src" / "app" / "demo"
    app_mod.mkdir(parents=True)
    (app_mod / "mod.py").write_text("def shared_fn():\n    return 2\n", encoding="utf-8")
    result = _mod.check_app_package_duplicate_function(tmp_path)
    assert result.ok is False
    assert "shared_fn" in result.detail


def test_cross_package_duplicate_class_allows_whitelisted_twins(tmp_path: Path) -> None:
    name = next(iter(_mod.INTENTIONAL_PARALLEL_CLASSES))
    for package in _mod.INTENTIONAL_PARALLEL_CLASSES[name]:
        _write_pkg_class(tmp_path, package, name)
    result = _mod.check_cross_package_duplicate_class(tmp_path)
    assert result.ok is True


def test_testpaths_complete_passes_when_listed(tmp_path: Path) -> None:
    (tmp_path / "packages" / "demo" / "tests").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths = ["packages/demo/tests"]\n',
        encoding="utf-8",
    )
    result = _mod.check_testpaths_complete(tmp_path)
    assert result.ok is True


def test_testpaths_complete_detects_missing(tmp_path: Path) -> None:
    (tmp_path / "packages" / "demo" / "tests").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths = ["app/tests"]\n',
        encoding="utf-8",
    )
    result = _mod.check_testpaths_complete(tmp_path)
    assert result.ok is False
    assert "packages/demo/tests" in result.detail


def test_topic_values_skips_prefix(tmp_path: Path) -> None:
    topics = tmp_path / "topics.py"
    topics.write_text(
        'TOPIC_CHAT_MESSAGE = "chat.message"\nTOPIC_EVENTSUB_PREFIX = "eventsub."\n',
        encoding="utf-8",
    )
    values = _mod.topic_values(topics)
    assert values == {"chat.message"}


def test_topic_literal_pattern_matches_exact_quoted_only() -> None:
    pattern = _mod.topic_literal_pattern({"chat.reply"})
    assert pattern is not None
    assert pattern.search('topic="chat.reply",') is not None
    # 出現在較長字串（如 docstring）中不應誤判
    assert pattern.search("規則：chat.message 轉 chat.reply。") is None


def test_check_topic_magic_strings_flags_literal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    topics = tmp_path / "topics.py"
    topics.write_text('TOPIC_CHAT_REPLY = "chat.reply"\n', encoding="utf-8")
    monkeypatch.setattr(_mod, "TOPICS_FILE", topics)
    src = tmp_path / "app" / "src" / "app"
    src.mkdir(parents=True)
    (src / "mod.py").write_text('event = make(topic="chat.reply")\n', encoding="utf-8")
    result = _mod.check_topic_magic_strings(tmp_path)
    assert result.ok is False
    assert "mod.py:1" in result.detail


def test_check_events_exports_passes(tmp_path: Path) -> None:
    init = tmp_path / "__init__.py"
    body = "\n".join(f'    "{name}",' for name in _mod.REQUIRED_EVENTS_EXPORTS)
    init.write_text(f"__all__ = [\n{body}\n]\n", encoding="utf-8")
    result = _mod.check_events_exports(init)
    assert result.ok is True


def test_check_events_exports_detects_missing(tmp_path: Path) -> None:
    init = tmp_path / "__init__.py"
    init.write_text('__all__ = ["ConfigChangedEvent"]\n', encoding="utf-8")
    result = _mod.check_events_exports(init)
    assert result.ok is False
    assert "TOPIC_CONFIG_CHANGED" in result.detail


def test_parse_main_list_processes() -> None:
    text = (
        "Publishers:\n"
        "  ingress-ttv-read       desc\n"
        "  (none)\n"
        "\n"
        "Subscribers:\n"
        "  sub-llm                desc\n"
    )
    assert _mod.parse_main_list_processes(text) == {"ingress-ttv-read", "sub-llm"}


def test_parse_stack_keys() -> None:
    src = (
        'PROCESS_STACKS: dict[str, tuple[str, ...]] = {\n'
        '    "ingress": STACK_INGRESS,\n'
        '    "ingress-chat": STACK_INGRESS_CHAT,\n'
        '    "status": STACK_STATUS,\n'
        "}\n"
        'TRAILING = {"not-a-stack": 1}\n'
    )
    assert _mod.parse_stack_keys(src) == {"ingress", "ingress-chat", "status"}


def test_parse_documented_processes() -> None:
    md = "| `ingress-ttv-read` | Pub | ✅ | `chat.message` | — |\n| not-a-row |\n"
    assert _mod.parse_documented_processes(md) == {"ingress-ttv-read"}


def test_print_results_pass(capsys: pytest.CaptureFixture[str]) -> None:
    code = _mod.print_results([_mod.CheckResult("demo", True, "ok")])
    captured = capsys.readouterr().out
    assert code == 0
    assert "PROJECT_AUDIT_PASS" in captured


def test_print_results_fail(capsys: pytest.CaptureFixture[str]) -> None:
    code = _mod.print_results([_mod.CheckResult("demo", False, "broken", hint="fix me")])
    captured = capsys.readouterr().out
    assert code == 1
    assert "PROJECT_AUDIT_FAIL" in captured
    assert "fix me" in captured


def test_run_checks_ci_skips_services(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def _ok(name: str):
        return lambda *_a, **_k: _mod.CheckResult(name, True, "")

    monkeypatch.setattr(_mod, "check_packages_no_app_import", _ok("a"))
    monkeypatch.setattr(_mod, "check_cross_package_duplicate_class", _ok("naming_pkg"))
    monkeypatch.setattr(_mod, "check_app_package_duplicate_class", _ok("naming_app"))
    monkeypatch.setattr(_mod, "check_cross_package_duplicate_function", _ok("naming_fn"))
    monkeypatch.setattr(_mod, "check_app_package_duplicate_function", _ok("naming_app_fn"))
    monkeypatch.setattr(_mod, "check_testpaths_complete", _ok("b"))
    monkeypatch.setattr(_mod, "check_topic_magic_strings", _ok("c"))
    monkeypatch.setattr(_mod, "check_events_exports", _ok("d"))
    monkeypatch.setattr(_mod, "check_control_builtins", _ok("e"))
    monkeypatch.setattr(_mod, "check_registry_drift", _ok("f"))
    monkeypatch.setattr(_mod, "check_stack_docs_drift", _ok("g"))
    monkeypatch.setattr(_mod, "check_repo_hygiene", _ok("h"))

    def _record_tool(*_a: object, **_k: object) -> _mod.CheckResult:
        calls.append("tool")
        return _mod.CheckResult("tool", True, "")

    monkeypatch.setattr(_mod, "run_ruff", _record_tool)
    monkeypatch.setattr(_mod, "run_pytest", _record_tool)
    monkeypatch.setattr(_mod, "load_verify_setup", lambda *_a, **_k: calls.append("verify"))

    results = _mod.run_checks(ci=True)
    assert [r.name for r in results] == [
        "a",
        "naming_pkg",
        "naming_app",
        "naming_fn",
        "naming_app_fn",
        "b",
        "c",
        "d",
        "e",
        "f",
        "g",
        "h",
    ]
    assert calls == []
