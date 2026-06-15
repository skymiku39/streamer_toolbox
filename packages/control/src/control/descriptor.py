from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReloadLevel = Literal["L0", "L1", "L2"]

MODULE_RULE_BOT = "rule-bot"
MODULE_LLM_BOT = "llm-bot"
MODULE_SHOW_OVERLAY = "show-overlay"
MODULE_VISUAL_EGRESS = "visual-egress"


@dataclass(frozen=True)
class ModuleDescriptor:
    module_id: str
    process_names: tuple[str, ...]
    config_files: tuple[str, ...]
    reload_level: ReloadLevel = "L1"
    dashboard_route: str | None = None

    def __post_init__(self) -> None:
        if not self.module_id:
            raise ValueError("module_id is required")
        if not self.process_names:
            raise ValueError("process_names must not be empty")
