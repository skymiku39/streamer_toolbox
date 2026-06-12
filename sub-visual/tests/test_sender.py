from pathlib import Path

from sub_visual.sender import FileSubtitleSender, build_sender


def test_file_sender_writes(tmp_path: Path) -> None:
    output = tmp_path / "out" / "subtitle.txt"
    sender = FileSubtitleSender(str(output))
    sender.send_text("hello subtitle")
    assert output.read_text(encoding="utf-8") == "hello subtitle"


def test_build_sender_defaults_to_file() -> None:
    sender, fallback = build_sender(backend="file", sender_name="test", output_file="x.txt")
    assert sender.backend_name == "file"
    assert fallback is None


def test_build_sender_spout2_falls_back_without_library() -> None:
    sender, fallback = build_sender(backend="spout2", sender_name="test", output_file="x.txt")
    assert sender.backend_name == "file"
    assert fallback is not None
