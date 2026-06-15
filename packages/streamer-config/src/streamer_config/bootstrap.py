"""初始化外部設定目錄（僅複製不存在的檔案）。"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from streamer_config.paths import ConfigPaths, repo_root


@dataclass
class BootstrapResult:
    root: Path
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "root": str(self.root),
            "created": list(self.created),
            "skipped": list(self.skipped),
        }


def _copy_if_missing(source: Path, target: Path, result: BootstrapResult) -> None:
    if target.exists():
        result.skipped.append(str(target))
        return
    if not source.is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    result.created.append(str(target))


def ensure_layout(
    directory: Path | str,
    *,
    channel: str | None = None,
    examples_root: Path | None = None,
) -> BootstrapResult:
    paths = ConfigPaths.from_dir(directory)
    root = examples_root or repo_root()
    result = BootstrapResult(root=paths.root)

    paths.root.mkdir(parents=True, exist_ok=True)
    paths.knowledge_dir.mkdir(parents=True, exist_ok=True)

    examples = root / "config" / "examples"
    config_dir = root / "config"
    knowledge_templates = config_dir / "knowledge"

    _copy_if_missing(examples / "bot_responses.example.json", paths.bot_responses, result)
    _copy_if_missing(
        examples / "redemption_responses.example.json",
        paths.redemption_responses,
        result,
    )
    _copy_if_missing(config_dir / "llm_subscriber.json", paths.llm_subscriber, result)
    _copy_if_missing(config_dir / "sub_visual.json", paths.sub_visual, result)

    channel_name = str(channel or "").strip().lower()
    if channel_name:
        knowledge_target = paths.knowledge_file(channel_name)
        template = knowledge_templates / f"{channel_name}.md"
        if not template.is_file():
            templates = sorted(knowledge_templates.glob("*.md"))
            template = templates[0] if templates else None
        if template is not None:
            _copy_if_missing(template, knowledge_target, result)

    return result
