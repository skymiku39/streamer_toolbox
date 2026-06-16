from __future__ import annotations

import pytest

from control import clear, register
from control.builtins import RULE_BOT, register_builtins
from control.descriptor import ModuleDescriptor


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    clear()
    yield
    clear()


def test_register_and_get() -> None:
    register(RULE_BOT)
    from control import get

    assert get("rule-bot") == RULE_BOT


def test_duplicate_module_id_rejected() -> None:
    register(RULE_BOT)
    duplicate = ModuleDescriptor(
        module_id="rule-bot",
        process_names=("other",),
        config_files=(),
    )
    with pytest.raises(ValueError, match="already registered"):
        register(duplicate)


def test_register_builtins_registers_all() -> None:
    register_builtins()
    from control import all_descriptors

    ids = {item.module_id for item in all_descriptors()}
    assert ids == {"rule-bot", "llm-bot", "show-overlay", "visual-egress"}
