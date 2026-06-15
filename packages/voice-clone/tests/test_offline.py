import os
import socket

import pytest

from voice_clone.config import Settings
from voice_clone.offline.guard import apply_offline_env, enable_network_block


def test_apply_offline_env() -> None:
    settings = Settings(offline=True)
    apply_offline_env(settings)
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"


def test_network_block_prevents_external_connection() -> None:
    enable_network_block()
    with pytest.raises(RuntimeError, match="離線模式禁止網路連線"):
        socket.create_connection(("8.8.8.8", 53), timeout=0.5)
