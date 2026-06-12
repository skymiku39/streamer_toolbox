import pytest

from sub_character_face.mapper import map_emotion_to_parameters


def test_happy_emotion_maps_smile() -> None:
    params = map_emotion_to_parameters("happy", 1.0)
    assert params["mouth_smile"] == 0.9
    assert params["eye_smile"] == 0.8


def test_intensity_scales_parameters() -> None:
    full = map_emotion_to_parameters("happy", 1.0)
    half = map_emotion_to_parameters("happy", 0.5)
    assert half["mouth_smile"] == pytest.approx(full["mouth_smile"] * 0.5)
    assert half["eye_smile"] == pytest.approx(full["eye_smile"] * 0.5)


def test_unknown_emotion_falls_back_to_neutral() -> None:
    params = map_emotion_to_parameters("unknown", 1.0)
    assert params["mouth_smile"] == 0.0


@pytest.mark.parametrize(
    ("emotion", "expected_key"),
    [
        ("angry", "brow_down"),
        ("sad", "eye_open"),
        ("surprised", "eye_wide"),
    ],
)
def test_emotion_presets_include_expected_keys(emotion: str, expected_key: str) -> None:
    params = map_emotion_to_parameters(emotion, 1.0)
    assert expected_key in params
