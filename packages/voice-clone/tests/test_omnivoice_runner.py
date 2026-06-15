from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from voice_clone.config import Settings
from voice_clone.inference.omnivoice_runner import OmniVoiceRunner


def test_synthesize_invokes_omnivoice_cli(tmp_path: Path) -> None:
    vendor = tmp_path / "vendor" / "OmniVoice"
    vendor.mkdir(parents=True)
    scripts = vendor / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "omnivoice-infer.exe").write_bytes(b"")

    settings = Settings(
        VOICE_CLONE_ROOT=tmp_path,
        OMNIVOICE_ROOT=vendor,
        VOICE_CLONE_NUM_STEP=16,
    )
    runner = OmniVoiceRunner(settings)

    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"RIFF")
    out = tmp_path / "out.wav"
    out.write_bytes(b"RIFF")

    with patch("voice_clone.inference.omnivoice_runner.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = runner.synthesize(
            model_id="k2-fsa/OmniVoice",
            ref_audio=ref,
            ref_text="參考文字",
            target_text="目標文字",
            output_path=out,
            language="Chinese",
        )

    assert result == out.resolve()
    cmd = mock_run.call_args.args[0]
    assert cmd[0].endswith("omnivoice-infer.exe")
    assert "--model" in cmd
    assert "--ref_audio" in cmd
    assert "--ref_text" in cmd
    assert "--num_step" in cmd
    assert "16" in cmd
    assert mock_run.call_args.kwargs["cwd"] == vendor


def test_runner_requires_vendor_root(tmp_path: Path) -> None:
    settings = Settings(
        VOICE_CLONE_ROOT=tmp_path,
        OMNIVOICE_ROOT=tmp_path / "missing-vendor",
    )
    with pytest.raises(FileNotFoundError, match="OmniVoice"):
        OmniVoiceRunner(settings)
