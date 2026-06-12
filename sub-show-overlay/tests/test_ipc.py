import json
from pathlib import Path

from sub_show_overlay.ipc import OverlaySnapshotWriter, read_overlay_snapshot


def test_snapshot_writer_round_trip(tmp_path: Path) -> None:
    ipc_path = tmp_path / "overlay.json"
    writer = OverlaySnapshotWriter(ipc_path, max_lines=5)
    writer.append_entry(
        {
            "plain_text": "Viewer: hello",
            "platform": "twitch",
            "segments": [{"type": "text", "text": "hello"}],
            "moderation_state": "visible",
            "author_name": "Viewer",
            "content": "hello",
        }
    )

    snapshot = read_overlay_snapshot(ipc_path)
    assert snapshot["content_revision"] == 1
    assert len(snapshot["lines"]) == 1
    assert snapshot["lines"][0]["plain_text"] == "Viewer: hello"

    on_disk = json.loads(ipc_path.read_text(encoding="utf-8"))
    assert on_disk["version"] == 3


def test_snapshot_writer_respects_max_lines(tmp_path: Path) -> None:
    ipc_path = tmp_path / "overlay.json"
    writer = OverlaySnapshotWriter(ipc_path, max_lines=20)
    for index in range(22):
        writer.append_entry(
            {
                "plain_text": f"line-{index}",
                "platform": "twitch",
                "segments": [{"type": "text", "text": f"line-{index}"}],
                "moderation_state": "visible",
            }
        )

    snapshot = read_overlay_snapshot(ipc_path)
    lines = [line["plain_text"] for line in snapshot["lines"]]
    assert len(lines) == 20
    assert lines[0] == "line-2"
    assert lines[-1] == "line-21"
