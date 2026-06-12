import json
from pathlib import Path

from sub_visual.config import SubtitleConfig


def test_from_dict_round_trip() -> None:
    data = {
        "backend": "file",
        "output_file": "custom.txt",
        "format_template": "{message}",
        "max_chars": 40,
        "filter": {
            "min_length": 2,
            "blocked_keywords": ["ad"],
            "block_commands": False,
            "block_urls": True,
        },
    }
    config = SubtitleConfig.from_dict(data)
    assert config.output_file == "custom.txt"
    assert config.max_chars == 40
    assert config.filter.min_length == 2
    assert config.filter.blocked_keywords == ["ad"]
    assert config.filter.block_commands is False
    assert config.filter.block_urls is True


def test_from_json_path_missing_returns_defaults(tmp_path: Path) -> None:
    config = SubtitleConfig.from_json_path(tmp_path / "missing.json")
    assert config.backend == "file"
    assert config.output_file == "obs_subtitle.txt"


def test_from_json_path_invalid_returns_defaults(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    config = SubtitleConfig.from_json_path(path)
    assert config.backend == "file"


def test_from_json_path_loads_file(tmp_path: Path) -> None:
    path = tmp_path / "sub_visual.json"
    path.write_text(
        json.dumps({"output_file": "live.txt", "max_chars": 50}),
        encoding="utf-8",
    )
    config = SubtitleConfig.from_json_path(path)
    assert config.output_file == "live.txt"
    assert config.max_chars == 50
