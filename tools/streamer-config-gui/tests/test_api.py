from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from streamer_config.bootstrap import ensure_layout
from streamer_config.paths import ConfigPaths
from streamer_config_gui.app import create_app


@pytest.fixture
def config_env(tmp_path):
    root = tmp_path / "repo"
    config = root / "config"
    examples = config / "examples"
    knowledge = config / "knowledge"
    examples.mkdir(parents=True)
    knowledge.mkdir(parents=True)
    (examples / "bot_responses.example.json").write_text(
        json.dumps({"schema_version": 2, "keyword": []}),
        encoding="utf-8",
    )
    (examples / "redemption_responses.example.json").write_text("{}", encoding="utf-8")
    (config / "llm_subscriber.json").write_text(
        json.dumps({"trigger_prefixes": ["!ask"], "context_window_minutes": 5}),
        encoding="utf-8",
    )
    (config / "sub_visual.json").write_text(
        json.dumps({"backend": "file", "filter": {"blocked_keywords": []}}),
        encoding="utf-8",
    )
    (knowledge / "demo.md").write_text("# demo", encoding="utf-8")

    user_dir = tmp_path / "user-config"
    ensure_layout(user_dir, channel="demo", examples_root=root)
    paths = ConfigPaths.from_dir(user_dir)
    app = create_app(paths=paths)
    return paths, TestClient(app)


def test_meta_lists_paths(config_env):
    paths, client = config_env
    response = client.get("/api/meta")
    assert response.status_code == 200
    payload = response.json()
    assert payload["paths"]["root"] == str(paths.root)
    assert len(payload["restart_hints"]) >= 4


def test_put_bot_responses_validates_and_saves(config_env):
    paths, client = config_env
    invalid = json.dumps({"schema_version": 2, "keyword": [{"trigger": "", "response": ""}]})
    bad = client.put("/api/bot-responses", json={"content": invalid})
    assert bad.status_code == 400

    valid = json.dumps(
        {
            "schema_version": 2,
            "keyword": [
                {
                    "trigger": "安安",
                    "response": "哈囉 {author}",
                    "match_mode": "contains",
                }
            ],
        }
    )
    ok = client.put("/api/bot-responses", json={"content": valid})
    assert ok.status_code == 200
    saved = json.loads(paths.bot_responses.read_text(encoding="utf-8"))
    assert saved["keyword"][0]["trigger"] == "安安"


def test_knowledge_round_trip(config_env):
    paths, client = config_env
    get_resp = client.get("/api/knowledge/demo.md")
    assert get_resp.status_code == 200
    assert get_resp.json()["content"] == "# demo"

    put_resp = client.put(
        "/api/knowledge/demo.md",
        json={"content": "# updated"},
    )
    assert put_resp.status_code == 200
    assert (paths.knowledge_dir / "demo.md").read_text(encoding="utf-8") == "# updated"
