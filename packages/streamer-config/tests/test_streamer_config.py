from __future__ import annotations

import json
from pathlib import Path

import pytest

from streamer_config.bootstrap import ensure_layout
from streamer_config.paths import ConfigPaths, resolve_path
from streamer_config.validate import ValidationError, validate_json_content


def test_config_paths_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("STREAMER_CONFIG_DIR", str(tmp_path))
    paths = ConfigPaths.from_env()
    assert paths is not None
    assert paths.bot_responses == tmp_path / "bot_responses.json"
    assert paths.knowledge_dir == tmp_path / "knowledge"


def test_resolve_path_prefers_explicit_env(tmp_path, monkeypatch):
    explicit = tmp_path / "custom.json"
    monkeypatch.setenv("BOT_RESPONSES_PATH", str(explicit))
    monkeypatch.setenv("STREAMER_CONFIG_DIR", str(tmp_path / "ignored"))
    resolved = resolve_path(
        "bot_responses",
        legacy_default=Path("legacy.json"),
    )
    assert resolved == explicit


def test_resolve_path_uses_config_dir_when_set(tmp_path, monkeypatch):
    monkeypatch.delenv("BOT_RESPONSES_PATH", raising=False)
    monkeypatch.setenv("STREAMER_CONFIG_DIR", str(tmp_path))
    resolved = resolve_path(
        "bot_responses",
        legacy_default=Path("legacy.json"),
    )
    assert resolved == tmp_path / "bot_responses.json"


def test_resolve_path_legacy_default(monkeypatch):
    monkeypatch.delenv("BOT_RESPONSES_PATH", raising=False)
    monkeypatch.delenv("STREAMER_CONFIG_DIR", raising=False)
    legacy = Path("legacy.json")
    resolved = resolve_path("bot_responses", legacy_default=legacy)
    assert resolved == legacy


def test_bootstrap_creates_files_without_overwrite(tmp_path):
    root = tmp_path / "repo"
    config = root / "config"
    examples = config / "examples"
    knowledge = config / "knowledge"
    examples.mkdir(parents=True)
    knowledge.mkdir(parents=True)
    (examples / "bot_responses.example.json").write_text('{"schema_version": 2}', encoding="utf-8")
    (examples / "redemption_responses.example.json").write_text("{}", encoding="utf-8")
    (config / "llm_subscriber.json").write_text("{}", encoding="utf-8")
    (config / "sub_visual.json").write_text("{}", encoding="utf-8")
    (knowledge / "demo.md").write_text("# demo", encoding="utf-8")

    target = tmp_path / "user-config"
    first = ensure_layout(target, channel="demo", examples_root=root)
    assert (target / "bot_responses.json").is_file()
    assert (target / "knowledge" / "demo.md").read_text(encoding="utf-8") == "# demo"
    assert len(first.created) >= 4

    (target / "bot_responses.json").write_text('{"custom": true}', encoding="utf-8")
    second = ensure_layout(target, channel="demo", examples_root=root)
    assert json.loads(
        (target / "bot_responses.json").read_text(encoding="utf-8")
    ) == {"custom": True}
    assert str(target / "bot_responses.json") in second.skipped


def test_validate_bot_responses_rejects_invalid_keyword():
    payload = {
        "schema_version": 2,
        "keyword": [{"trigger": "", "response": "hi", "match_mode": "bad"}],
    }
    with pytest.raises(ValidationError) as exc:
        validate_json_content("bot_responses.json", json.dumps(payload))
    assert any("trigger" in item for item in exc.value.errors)
    assert any("match_mode" in item for item in exc.value.errors)
