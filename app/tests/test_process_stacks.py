from app.processes.stacks import PROCESS_STACKS, resolve_stack


def test_resolve_stack_ingress_includes_twitch_stream() -> None:
    names = resolve_stack("ingress")
    assert "ingress-twitch-stream" in names
    assert "ingress-ttv-read" in names
    assert "sub-stream-record" in names


def test_resolve_stack_llm() -> None:
    names = resolve_stack("llm")
    assert names == [
        "sub-llm",
        "sub-qa-memory-structured",
        "sub-qa-memory-batch",
        "twitch-connector",
    ]


def test_process_stacks_keys() -> None:
    assert set(PROCESS_STACKS) == {"ingress", "status", "llm"}


def test_resolve_stack_status() -> None:
    names = resolve_stack("status")
    assert names == ["sub-live-status", "twitch-connector"]
