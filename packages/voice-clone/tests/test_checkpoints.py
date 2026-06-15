from voice_clone.config import Settings
from voice_clone.inference.checkpoints import resolve_model_bundle


def test_resolve_model_bundle_default(tmp_path) -> None:
    settings = Settings(VOICE_CLONE_ROOT=tmp_path)
    bundle = resolve_model_bundle(settings=settings)
    assert bundle.model_id == "k2-fsa/OmniVoice"


def test_resolve_model_bundle_custom() -> None:
    bundle = resolve_model_bundle(model_id="k2-fsa/OmniVoice")
    assert bundle.model_id == "k2-fsa/OmniVoice"
