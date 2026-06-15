from __future__ import annotations

from control.descriptor import (
    MODULE_LLM_BOT,
    MODULE_RULE_BOT,
    MODULE_SHOW_OVERLAY,
    MODULE_VISUAL_EGRESS,
    ModuleDescriptor,
)
from control.registry import get, register

RULE_BOT = ModuleDescriptor(
    module_id=MODULE_RULE_BOT,
    process_names=("sub-bot-logic",),
    config_files=("bot_responses.json", "redemption_responses.json"),
    reload_level="L1",
    dashboard_route="/rule-bot",
)

LLM_BOT = ModuleDescriptor(
    module_id=MODULE_LLM_BOT,
    process_names=("sub-llm", "sub-qa-memory-structured", "sub-qa-memory-batch"),
    config_files=("llm_subscriber.json",),
    reload_level="L1",
    dashboard_route="/llm-bot",
)

SHOW_OVERLAY = ModuleDescriptor(
    module_id=MODULE_SHOW_OVERLAY,
    process_names=("sub-show-overlay",),
    config_files=(),
    reload_level="L2",
    dashboard_route="/show-overlay",
)

VISUAL_EGRESS = ModuleDescriptor(
    module_id=MODULE_VISUAL_EGRESS,
    process_names=("sub-visual",),
    config_files=("sub_visual.json",),
    reload_level="L1",
    dashboard_route="/visual-egress",
)

CONFIG_FILE_MODULE_ID: dict[str, str] = {
    "bot_responses.json": MODULE_RULE_BOT,
    "redemption_responses.json": MODULE_RULE_BOT,
    "llm_subscriber.json": MODULE_LLM_BOT,
    "sub_visual.json": MODULE_VISUAL_EGRESS,
}


def register_builtins() -> None:
    for descriptor in (RULE_BOT, LLM_BOT, SHOW_OVERLAY, VISUAL_EGRESS):
        if get(descriptor.module_id) is None:
            register(descriptor)
