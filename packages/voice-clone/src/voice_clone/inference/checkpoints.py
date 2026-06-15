from __future__ import annotations

from dataclasses import dataclass

from voice_clone.config import Settings, get_settings

DEFAULT_MODEL_ID = "k2-fsa/OmniVoice"


@dataclass(frozen=True)
class ModelBundle:
    model_id: str


def resolve_model_bundle(
    *,
    model_id: str | None = None,
    settings: Settings | None = None,
) -> ModelBundle:
    settings = settings or get_settings()
    resolved = (model_id or settings.default_model).strip()
    if not resolved:
        raise ValueError("請指定 --model 或設定 VOICE_CLONE_MODEL")
    return ModelBundle(model_id=resolved)
