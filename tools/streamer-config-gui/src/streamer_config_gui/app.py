"""FastAPI application for local config editing."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from control import CONFIG_FILE_MODULE_ID
from control.publisher import try_publish_config_changed
from streamer_config.bootstrap import ensure_layout
from streamer_config.paths import ConfigPaths, default_config_dir
from streamer_config.validate import (
    ValidationError,
    validate_json_content,
    validate_knowledge_filename,
)

RESTART_HINTS = [
    {"file": "knowledge/*.md", "process": "sub-llm"},
]

STATIC_DIR = Path(__file__).resolve().parent / "static"


class TextPayload(BaseModel):
    content: str


def _load_paths() -> ConfigPaths:
    load_dotenv()
    raw = os.environ.get("STREAMER_CONFIG_DIR", "").strip()
    if raw:
        return ConfigPaths.from_dir(raw)
    return ConfigPaths.from_dir(default_config_dir())


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"file not found: {path}")
    return path.read_text(encoding="utf-8")


def _write_json(path: Path, content: str) -> dict[str, Any]:
    try:
        payload = validate_json_content(path.name, content)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail={"errors": exc.errors}) from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def _save_json_config(path: Path, content: str) -> dict[str, Any]:
    payload = _write_json(path, content)
    module_id = CONFIG_FILE_MODULE_ID.get(path.name)
    if module_id:
        try_publish_config_changed(module_id=module_id, config_file=path.name)
    return payload


def _saved_reload_response() -> dict[str, str]:
    return {"status": "saved", "reload": "config.changed"}


def create_app(*, paths: ConfigPaths | None = None) -> FastAPI:
    config_paths = paths or _load_paths()
    app = FastAPI(title="Streamer Config GUI", docs_url="/api/docs")

    @app.get("/api/meta")
    def meta() -> dict[str, Any]:
        channel = os.environ.get("TWITCH_CHANNEL", "").strip()
        knowledge_file = None
        if channel:
            try:
                knowledge_file = str(config_paths.knowledge_file(channel))
            except ValueError:
                knowledge_file = None
        return {
            "paths": config_paths.to_dict(),
            "channel": channel,
            "knowledge_file": knowledge_file,
            "restart_hints": RESTART_HINTS,
        }

    @app.post("/api/bootstrap")
    def bootstrap() -> dict[str, Any]:
        channel = os.environ.get("TWITCH_CHANNEL", "").strip() or None
        result = ensure_layout(config_paths.root, channel=channel)
        return result.to_dict()

    @app.get("/api/bot-responses")
    def get_bot_responses() -> dict[str, str]:
        return {"content": _read_text(config_paths.bot_responses)}

    @app.put("/api/bot-responses")
    def put_bot_responses(payload: TextPayload) -> dict[str, str]:
        _save_json_config(config_paths.bot_responses, payload.content)
        return _saved_reload_response()

    @app.get("/api/redemption-responses")
    def get_redemption_responses() -> dict[str, str]:
        return {"content": _read_text(config_paths.redemption_responses)}

    @app.put("/api/redemption-responses")
    def put_redemption_responses(payload: TextPayload) -> dict[str, str]:
        _save_json_config(config_paths.redemption_responses, payload.content)
        return _saved_reload_response()

    @app.get("/api/llm-subscriber")
    def get_llm_subscriber() -> dict[str, str]:
        return {"content": _read_text(config_paths.llm_subscriber)}

    @app.put("/api/llm-subscriber")
    def put_llm_subscriber(payload: TextPayload) -> dict[str, str]:
        _save_json_config(config_paths.llm_subscriber, payload.content)
        return _saved_reload_response()

    @app.get("/api/sub-visual")
    def get_sub_visual() -> dict[str, str]:
        return {"content": _read_text(config_paths.sub_visual)}

    @app.put("/api/sub-visual")
    def put_sub_visual(payload: TextPayload) -> dict[str, str]:
        _save_json_config(config_paths.sub_visual, payload.content)
        return _saved_reload_response()

    @app.get("/api/knowledge")
    def list_knowledge() -> dict[str, list[str]]:
        config_paths.knowledge_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(path.name for path in config_paths.knowledge_dir.glob("*.md"))
        return {"files": files}

    @app.get("/api/knowledge/{filename}")
    def get_knowledge(filename: str) -> dict[str, str]:
        try:
            validate_knowledge_filename(filename)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail={"errors": exc.errors}) from exc
        return {"content": _read_text(config_paths.knowledge_dir / filename)}

    @app.put("/api/knowledge/{filename}")
    def put_knowledge(filename: str, payload: TextPayload) -> dict[str, str]:
        try:
            validate_knowledge_filename(filename)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail={"errors": exc.errors}) from exc
        target = config_paths.knowledge_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload.content, encoding="utf-8")
        return {"status": "saved", "restart": "sub-llm"}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
