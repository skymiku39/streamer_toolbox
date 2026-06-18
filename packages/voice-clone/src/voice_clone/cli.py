from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from bus import LocalEventBus
from voice_clone.audio.preprocess import preprocess_sample_audio
from voice_clone.config import get_settings
from voice_clone.inference.checkpoints import resolve_model_bundle
from voice_clone.inference.engine import InferenceEngine
from voice_clone.inference.sample_ref import resolve_sample_reference
from voice_clone.offline.guard import offline_context

app = typer.Typer(
    name="voice-clone",
    help="離線語音克隆：提供樣本音檔即可合成輸出（OmniVoice）",
    no_args_is_help=True,
)


def _bus() -> LocalEventBus:
    bus = LocalEventBus()

    def log_event(payload: dict) -> None:
        typer.echo(str(payload))

    bus.subscribe("synthesis.completed", log_event)
    return bus


def _require_stt_extra() -> None:
    try:
        import faster_whisper  # noqa: F401
    except ImportError as exc:
        raise typer.BadParameter("需要 STT 套件：uv sync --extra stt") from exc


@app.command("clone")
def clone(
    sample: Annotated[Path, typer.Argument(help="參考樣本音檔（建議 3–10 秒）")],
    text: Annotated[str, typer.Option("--text", "-t", help="要合成的目標文字")],
    output: Annotated[Path | None, typer.Option("--out", "-o", help="輸出 wav 路徑")] = None,
    sample_text: Annotated[
        str | None,
        typer.Option("--sample-text", help="樣本音檔對應文字（可省略，由 OmniVoice 自動轉寫）"),
    ] = None,
    stt: Annotated[
        bool,
        typer.Option("--stt", help="以本機 STT 轉寫樣本（未提供 sample-text 時）"),
    ] = False,
    model: Annotated[
        str | None,
        typer.Option("--model", help="HuggingFace 模型 ID（預設 k2-fsa/OmniVoice）"),
    ] = None,
    language: Annotated[
        str | None,
        typer.Option("--language", help="合成語言（預設 Chinese）"),
    ] = None,
    device: Annotated[str | None, typer.Option("--device", help="推理裝置，如 cuda:0")] = None,
    num_step: Annotated[
        int | None,
        typer.Option("--num-step", help="擴散步數（16 較快，32 品質較好）"),
    ] = None,
    denoise: Annotated[
        bool,
        typer.Option("--denoise/--no-denoise", help="樣本音檔前處理降噪"),
    ] = True,
    trim_silence: Annotated[
        bool,
        typer.Option("--trim-silence/--no-trim-silence", help="修剪樣本頭尾靜音"),
    ] = True,
) -> None:
    """提供樣本音檔即可合成：OmniVoice 零樣本語音克隆（fp16，較省 VRAM）。"""
    settings = get_settings()
    updates: dict = {}
    if device:
        updates["device"] = device
    if language:
        updates["language"] = language
    if num_step is not None:
        updates["num_step"] = num_step
    if updates:
        settings = settings.model_copy(update=updates)
    out_path = output or Path("output.wav")

    stt_worker = None
    ref_text: str | None = sample_text
    if not ref_text and stt:
        _require_stt_extra()
        from voice_clone.stt.config import SttConfig
        from voice_clone.stt.worker import OfflineSTTWorker

        stt_worker = OfflineSTTWorker(SttConfig.from_env())
        stt_worker.preload_in_background()
        if not stt_worker.wait_until_ready(timeout=120.0):
            raise typer.BadParameter("STT 模型載入失敗，請確認 faster-whisper 已安裝")

    with offline_context(settings):
        if ref_text or stt_worker is not None:
            try:
                reference = resolve_sample_reference(
                    sample,
                    sample_text=ref_text,
                    stt_worker=stt_worker,
                )
            except ValueError as exc:
                raise typer.BadParameter(str(exc)) from exc
            ref_text = reference.text
            source_audio = reference.source_audio_path or reference.audio_path
        else:
            source_audio = sample.resolve()
            if not source_audio.exists():
                raise typer.BadParameter(f"找不到樣本音檔：{source_audio}")

        cache_dir = out_path.parent / ".voice_clone_cache"
        prepared_audio = preprocess_sample_audio(
            source_audio,
            cache_dir=cache_dir,
            denoise=denoise,
            trim_silence=trim_silence,
            denoise_hp_hz=settings.denoise_hp_hz,
            denoise_gate_ratio=settings.denoise_gate_ratio,
        )
        bundle = resolve_model_bundle(model_id=model, settings=settings)
        engine = InferenceEngine(bus=_bus(), settings=settings)
        payload = engine.synthesize(
            text,
            out_path,
            bundle=bundle,
            ref_audio=prepared_audio,
            ref_text=ref_text,
            language=settings.language,
            num_step=settings.num_step,
        )
        typer.echo(f"樣本：{source_audio}")
        if prepared_audio != source_audio:
            typer.echo(f"前處理：{prepared_audio}")
        if ref_text:
            typer.echo(f"參考文字：{ref_text}")
        else:
            typer.echo("參考文字：由 OmniVoice 自動轉寫")
        typer.echo(f"模型：{bundle.model_id}")
        typer.echo(f"合成完成：{payload.output_path}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
