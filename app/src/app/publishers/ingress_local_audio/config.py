from __future__ import annotations

import os
from dataclasses import dataclass

from ingress_twitch_audio.config import SttConfig


def _parse_audio_device(raw: str) -> int | str | None:
    value = raw.strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    return value


@dataclass(frozen=True)
class LocalAudioConfig:
    stt: SttConfig
    device: int | str | None

    @classmethod
    def from_env(cls) -> LocalAudioConfig:
        return cls(
            stt=SttConfig.from_env(),
            device=_parse_audio_device(os.environ.get("LOCAL_AUDIO_DEVICE", "")),
        )
