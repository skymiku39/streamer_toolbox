from __future__ import annotations

import logging
import sys
from typing import Protocol, runtime_checkable

from sub_character_stage.cue import StageCue

logger = logging.getLogger(__name__)

OBS_MEDIA_ACTION_RESTART = "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART"


@runtime_checkable
class StageDriver(Protocol):
    def play_turn(self, cue: StageCue) -> None: ...

    def close(self) -> None: ...


class LogStageDriver:
    def play_turn(self, cue: StageCue) -> None:
        expression = "none"
        if cue.expression is not None:
            expression = f"{cue.expression.driver} {cue.expression.parameters}"
        fallback = " (audio-only fallback)" if cue.expression_fallback else ""
        print(
            f"[stage] turn={cue.turn_id} audio={cue.audio.audio_path} "
            f"duration_ms={cue.audio.duration_ms} expression={expression}{fallback}",
            file=sys.stderr,
            flush=True,
        )

    def close(self) -> None:
        return None


class ObsWebSocketStageDriver:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        password: str,
        scene_name: str,
        media_source: str,
    ) -> None:
        import obsws_python as obs

        self._client = obs.ReqClient(host=host, port=port, password=password, timeout=5)
        self._scene_name = scene_name
        self._media_source = media_source

    def play_turn(self, cue: StageCue) -> None:
        if self._scene_name:
            self._client.set_current_program_scene(self._scene_name)
        self._client.set_input_settings(
            self._media_source,
            {"local_file": cue.audio.audio_path},
            overlay=True,
        )
        self._client.trigger_media_input_action(self._media_source, OBS_MEDIA_ACTION_RESTART)
        if cue.expression is not None:
            logger.info(
                "expression ready for turn=%s driver=%s params=%s",
                cue.turn_id,
                cue.expression.driver,
                cue.expression.parameters,
            )

    def close(self) -> None:
        return None


def create_stage_driver(
    driver_name: str,
    *,
    obs_host: str,
    obs_port: int,
    obs_password: str,
    obs_scene: str,
    obs_media_source: str,
) -> StageDriver:
    if driver_name == "log":
        return LogStageDriver()
    if driver_name == "obs":
        return ObsWebSocketStageDriver(
            host=obs_host,
            port=obs_port,
            password=obs_password,
            scene_name=obs_scene,
            media_source=obs_media_source,
        )
    raise ValueError(f"unsupported stage driver: {driver_name!r}")
