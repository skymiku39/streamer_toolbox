from __future__ import annotations

import sys


class Sapi5TtsEngine:
    """Windows SAPI5 SpVoice 實作。"""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Sapi5TtsEngine is only available on Windows")
        try:
            import win32com.client
        except ImportError as exc:
            raise RuntimeError(
                "pywin32 is required for SAPI5; install with: uv sync --package pkg-tts --extra sapi5"
            ) from exc
        self._voice = win32com.client.Dispatch("SAPI.SpVoice")

    def speak(self, text: str) -> None:
        # 0 = SVSFDefault，同步阻塞至朗讀完成
        self._voice.Speak(text, 0)
