"""設定目錄路徑解析。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ENV_STREAMER_CONFIG_DIR = "STREAMER_CONFIG_DIR"

BOT_RESPONSES_NAME = "bot_responses.json"
REDEMPTION_RESPONSES_NAME = "redemption_responses.json"
LLM_SUBSCRIBER_NAME = "llm_subscriber.json"
SUB_VISUAL_NAME = "sub_visual.json"
CHARACTER_BRAIN_NAME = "character_brain.json"
KNOWLEDGE_DIR_NAME = "knowledge"

PATH_ENV_KEYS: dict[str, str] = {
    "bot_responses": "BOT_RESPONSES_PATH",
    "redemption_responses": "BOT_REDEMPTIONS_PATH",
    "llm_subscriber": "LLM_SUBSCRIBER_CONFIG",
    "sub_visual": "VISUAL_CONFIG_PATH",
    "character_brain": "CHARACTER_BRAIN_CONFIG",
    "knowledge_dir": "LLM_KNOWLEDGE_PATH",
}


def repo_root() -> Path:
    """Resolve streamer_toolbox repository root from package location."""
    return Path(__file__).resolve().parents[4]


def default_config_dir() -> Path:
    return Path.home() / "streamer-config"


def _expand_path(raw: str) -> Path:
    return Path(os.path.expandvars(raw)).expanduser()


def _env_map(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


@dataclass(frozen=True)
class ConfigPaths:
    """Resolved paths under STREAMER_CONFIG_DIR."""

    root: Path

    @property
    def bot_responses(self) -> Path:
        return self.root / BOT_RESPONSES_NAME

    @property
    def redemption_responses(self) -> Path:
        return self.root / REDEMPTION_RESPONSES_NAME

    @property
    def llm_subscriber(self) -> Path:
        return self.root / LLM_SUBSCRIBER_NAME

    @property
    def sub_visual(self) -> Path:
        return self.root / SUB_VISUAL_NAME

    @property
    def character_brain(self) -> Path:
        return self.root / CHARACTER_BRAIN_NAME

    @property
    def knowledge_dir(self) -> Path:
        return self.root / KNOWLEDGE_DIR_NAME

    def knowledge_file(self, channel: str) -> Path:
        safe = str(channel or "").strip().lower()
        if not safe:
            raise ValueError("channel name is required for knowledge file path")
        return self.knowledge_dir / f"{safe}.md"

    @classmethod
    def from_dir(cls, directory: Path | str) -> ConfigPaths:
        return cls(root=_expand_path(str(directory)))

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ConfigPaths | None:
        values = _env_map(env)
        raw = values.get(ENV_STREAMER_CONFIG_DIR, "").strip()
        if not raw:
            return None
        return cls.from_dir(_expand_path(raw))

    def to_dict(self) -> dict[str, str]:
        return {
            "root": str(self.root),
            "bot_responses": str(self.bot_responses),
            "redemption_responses": str(self.redemption_responses),
            "llm_subscriber": str(self.llm_subscriber),
            "sub_visual": str(self.sub_visual),
            "character_brain": str(self.character_brain),
            "knowledge_dir": str(self.knowledge_dir),
        }


def resolve_path(
    key: str,
    *,
    env: Mapping[str, str] | None = None,
    legacy_default: Path,
) -> Path:
    """Resolve a config path: explicit env > STREAMER_CONFIG_DIR > legacy default."""
    if key not in PATH_ENV_KEYS:
        raise KeyError(f"unknown config path key: {key}")

    values = _env_map(env)
    explicit = values.get(PATH_ENV_KEYS[key], "").strip()
    if explicit:
        return _expand_path(explicit)

    config_paths = ConfigPaths.from_env(values)
    if config_paths is not None:
        if key == "knowledge_dir":
            return config_paths.knowledge_dir
        return getattr(config_paths, key)

    return legacy_default
