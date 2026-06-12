from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class FilterConfig:
    min_length: int = 0
    blocked_keywords: list[str] = field(default_factory=list)
    block_commands: bool = True
    block_urls: bool = False

    def __post_init__(self) -> None:
        if self.min_length < 0:
            raise ValueError("min_length must be >= 0")


@dataclass
class SubtitleConfig:
    backend: str = "file"
    sender_name: str = "StreamerToolboxSubtitle"
    output_file: str = "obs_subtitle.txt"
    format_template: str = "{username}: {message}"
    max_chars: int = 80
    filter: FilterConfig = field(default_factory=FilterConfig)

    def __post_init__(self) -> None:
        if self.max_chars < 1:
            raise ValueError("max_chars must be >= 1")
        if self.backend not in {"file", "spout2"}:
            raise ValueError(f"unsupported backend: {self.backend}")

    def to_dict(self) -> dict:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> SubtitleConfig:
        filter_data = data.get("filter", {})
        return cls(
            backend=data.get("backend", "file"),
            sender_name=data.get("sender_name", "StreamerToolboxSubtitle"),
            output_file=data.get("output_file", "obs_subtitle.txt"),
            format_template=data.get("format_template", "{username}: {message}"),
            max_chars=int(data.get("max_chars", 80)),
            filter=FilterConfig(
                min_length=int(filter_data.get("min_length", 0)),
                blocked_keywords=list(filter_data.get("blocked_keywords", [])),
                block_commands=bool(filter_data.get("block_commands", True)),
                block_urls=bool(filter_data.get("block_urls", False)),
            ),
        )

    @classmethod
    def from_json_path(cls, path: Path) -> SubtitleConfig:
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except (json.JSONDecodeError, TypeError, ValueError):
            return cls()
