from __future__ import annotations

from unittest.mock import MagicMock, patch

from events import CharacterAudioReadyEvent, CharacterExpressionReadyEvent

from sub_character_stage.cue import StageCue
from sub_character_stage.driver import ObsWebSocketStageDriver


def _cue() -> StageCue:
    audio = CharacterAudioReadyEvent(
        schema_version=1,
        topic="character.audio.ready",
        turn_id="turn-1",
        audio_path="C:/audio/turn-1.wav",
        duration_ms=1200,
    )
    expression = CharacterExpressionReadyEvent(
        schema_version=1,
        topic="character.expression.ready",
        turn_id="turn-1",
        driver="vts",
        parameters={"mouth_smile": 0.8},
    )
    return StageCue(
        turn_id="turn-1",
        audio=audio,
        expression=expression,
        expression_fallback=False,
    )


@patch("obsws_python.ReqClient")
def test_obs_stage_driver_updates_media_source(mock_req_client) -> None:
    client = MagicMock()
    mock_req_client.return_value = client
    driver = ObsWebSocketStageDriver(
        host="localhost",
        port=4455,
        password="secret",
        scene_name="Main",
        media_source="CharacterAudio",
    )
    driver.play_turn(_cue())

    client.set_current_program_scene.assert_called_once_with("Main")
    client.set_input_settings.assert_called_once()
    client.trigger_media_input_action.assert_called_once()
