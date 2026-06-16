from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class SubtitleSender(Protocol):
    backend_name: str

    def send_text(self, text: str) -> None: ...

    def close(self) -> None: ...


class FileSubtitleSender:
    backend_name = "file"

    def __init__(self, output_file: str) -> None:
        self.output_path = Path(output_file)
        if not self.output_path.is_absolute():
            self.output_path = Path.cwd() / self.output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def send_text(self, text: str) -> None:
        self.output_path.write_text(text, encoding="utf-8")

    def close(self) -> None:
        return None


class Spout2SubtitleSender:
    """嘗試動態接上 Spout2；不可用時由 service 降級為 file。"""

    backend_name = "spout2"

    def __init__(self, sender_name: str) -> None:
        self.sender_name = sender_name
        self._impl = None
        self._error: str | None = None

        try:
            import SpoutGL  # type: ignore[import-not-found]

            if hasattr(SpoutGL, "SpoutSender"):
                self._impl = SpoutGL.SpoutSender()
                if hasattr(self._impl, "setSenderName"):
                    self._impl.setSenderName(sender_name)
                elif hasattr(self._impl, "SetSenderName"):
                    self._impl.SetSenderName(sender_name)
            else:
                self._error = "SpoutGL 缺少 SpoutSender"
        except Exception as exc:  # pragma: no cover - 依環境而定
            self._error = str(exc)

    @property
    def available(self) -> bool:
        return self._impl is not None

    @property
    def error(self) -> str:
        return self._error or ""

    def send_text(self, text: str) -> None:
        if not self._impl:
            raise RuntimeError(self.error or "Spout2 不可用")

        if hasattr(self._impl, "sendText"):
            self._impl.sendText(text)
            return
        if hasattr(self._impl, "SendText"):
            self._impl.SendText(text)
            return
        raise RuntimeError("目前 Spout2 Python 套件未提供文字傳送 API")

    def close(self) -> None:
        if self._impl and hasattr(self._impl, "ReleaseSender"):
            self._impl.ReleaseSender()


def build_sender(
    *, backend: str, sender_name: str, output_file: str
) -> tuple[SubtitleSender, str | None]:
    """建立輸出後端；若 spout2 不可用則回傳 file 與降級原因。"""
    if backend == "spout2":
        spout_sender = Spout2SubtitleSender(sender_name=sender_name)
        if spout_sender.available:
            return spout_sender, None
        return FileSubtitleSender(output_file=output_file), spout_sender.error
    return FileSubtitleSender(output_file=output_file), None
