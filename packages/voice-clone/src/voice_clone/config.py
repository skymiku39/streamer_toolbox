from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", str(_project_root() / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    voice_clone_root: Path = Field(default_factory=_project_root, alias="VOICE_CLONE_ROOT")
    omnivoice_root: Path = Field(default=Path("./vendor/OmniVoice"), alias="OMNIVOICE_ROOT")
    default_model: str = Field(default="k2-fsa/OmniVoice", alias="VOICE_CLONE_MODEL")
    language: str = Field(default="Chinese", alias="VOICE_CLONE_LANGUAGE")
    offline: bool = Field(default=True, alias="VOICE_CLONE_OFFLINE")
    device: str = Field(default="cuda:0", alias="VOICE_CLONE_DEVICE")
    num_step: int = Field(default=16, alias="VOICE_CLONE_NUM_STEP")
    target_sample_rate: int = Field(default=24000, alias="VOICE_CLONE_SAMPLE_RATE")
    denoise_sample: bool = Field(default=True, alias="VOICE_CLONE_DENOISE")
    trim_silence_sample: bool = Field(default=True, alias="VOICE_CLONE_TRIM_SILENCE")
    denoise_hp_hz: float = Field(default=100.0, alias="VOICE_CLONE_DENOISE_HP_HZ")
    denoise_gate_ratio: float = Field(default=0.12, alias="VOICE_CLONE_DENOISE_GATE_RATIO")

    def resolve(self, path: Path) -> Path:
        if path.is_absolute():
            return path
        return (self.voice_clone_root / path).resolve()

    @property
    def resolved_omnivoice_root(self) -> Path:
        return self.resolve(self.omnivoice_root)


@lru_cache
def get_settings() -> Settings:
    return Settings()
