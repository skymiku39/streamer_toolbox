from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from voice_clone.config import Settings, get_settings


class OmniVoiceRunner:
    """以 subprocess 呼叫 vendor/OmniVoice 的 omnivoice-infer。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self.root = self._settings.resolved_omnivoice_root
        if not self.root.exists():
            raise FileNotFoundError(
                f"OmniVoice 不存在：{self.root}\n"
                "請執行：git submodule update --init && scripts/setup_omnivoice.ps1"
            )

    def synthesize(
        self,
        *,
        model_id: str,
        ref_audio: Path,
        ref_text: str | None,
        target_text: str,
        output_path: Path,
        language: str | None = None,
        device: str | None = None,
        num_step: int | None = None,
    ) -> Path:
        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self._resolve_omnivoice_infer(),
            "--model",
            model_id,
            "--text",
            target_text,
            "--ref_audio",
            str(ref_audio.resolve()),
            "--output",
            str(output_path),
            "--language",
            language or self._settings.language,
            "--num_step",
            str(num_step if num_step is not None else self._settings.num_step),
        ]
        if ref_text and ref_text.strip():
            cmd.extend(["--ref_text", ref_text.strip()])
        if device or self._settings.device:
            cmd.extend(["--device", device or self._settings.device])

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        result = subprocess.run(
            cmd,
            cwd=self.root,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"OmniVoice 推理失敗 exit={result.returncode}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        if not output_path.exists():
            raise RuntimeError(
                f"推理完成但未產生輸出檔：{output_path}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return output_path

    def _resolve_omnivoice_infer(self) -> str:
        scripts = (
            self.root / ".venv" / "Scripts" / "omnivoice-infer.exe",
            self.root / ".venv" / "bin" / "omnivoice-infer",
        )
        for script in scripts:
            if script.exists():
                return str(script)
        return "omnivoice-infer"

    def _resolve_python(self) -> str:
        candidates = (
            self.root / ".venv" / "Scripts" / "python.exe",
            self.root / ".venv" / "bin" / "python",
        )
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return sys.executable
