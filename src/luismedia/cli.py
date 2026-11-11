"""CLI multiplataforma. A GUI (qualquer que seja) chama o mesmo Core.

    luismedia doctor                      # checa ffmpeg, GPU, Ollama, modelo
    luismedia run aula1.mp4 aula2.mp4 -o saida/ --profile curso.yaml
    luismedia run entrada/Aula1 -o saida/ --json-events   # progresso em JSON Lines
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .adapters import ffmpeg as ff
from .adapters.ollama import OllamaClient
from .core.config import Encoder, Settings
from .core.errors import LuisMediaError
from .core.logging import setup_logging

VIDEO_EXT = {".mp4", ".mkv", ".mov", ".m4v", ".webm"}


def _collect(inputs: list[Path]) -> list[Path]:
    found: list[Path] = []
    for p in inputs:
        if p.is_dir():
            found += sorted(f for f in p.rglob("*") if f.suffix.lower() in VIDEO_EXT
                            and not f.stem.endswith(("_DINAMICO", "_LEGENDADO")))
        elif p.suffix.lower() in VIDEO_EXT:
            found.append(p)
    return found


def cmd_doctor(settings: Settings) -> int:
    checks: list[tuple[str, bool, str]] = []
    for b in ("ffmpeg", "ffprobe"):
        try:
            checks.append((b, True, ff.find_binary(b)))
        except LuisMediaError as e:
            checks.append((b, False, str(e)))
    if checks[0][1]:
        for enc in (Encoder.NVIDIA, Encoder.AMD, Encoder.INTEL):
            checks.append((f"encoder {enc.value}", ff.encoder_works(enc), "teste de 1 frame"))
    try:
        import faster_whisper  # noqa: F401

        from .adapters.whisper import detect_device

        checks.append(("faster-whisper", True, "dispositivo: {}/{}".format(*detect_device(settings.whisper.device))))
    except ImportError:
        checks.append(("faster-whisper", False, "pip install 'luismedia[whisper]'"))
    client = OllamaClient(settings.llm)
    up = client.is_running()
    checks.append(("ollama", up, settings.llm.base_url))
    if up:
        checks.append((f"modelo {settings.llm.model}", client.has_model(), "ollama pull " + settings.llm.model))

    try:
        from .adapters.pdf import find_browser

        checks.append(("navegador (PDF)", True, find_browser()))
    except LuisMediaError as e:
        checks.append(("navegador (PDF)", False, str(e)))

    for name, ok, info in checks:
        print(f"  [{'OK' if ok else '--'}] {name:<22} {info}")
    essential = all(ok for name, ok, _ in checks if name in {"ffmpeg", "ffprobe", "faster-whisper"})
    return 0 if essential else 1


def cmd_run(settings: Settings, inputs: list[Path], out: Path, json_events: bool) -> int:
    from .pipeline.runner import Pipeline, ProgressEvent

    videos = _collect(inputs)
    if not videos:
        print("Nenhum video encontrado.", file=sys.stderr)
        return 2

    def printer(evt: ProgressEvent) -> None:
        if json_events:
            print(json.dumps(asdict(evt), ensure_ascii=False), flush=True)
        elif evt.status != "running" or evt.progress == 0.0:
            print(f"[{evt.index}/{evt.total}] {evt.video} | {evt.stage}: {evt.status} {evt.message}".rstrip(),
                  flush=True)

    results = Pipeline(settings, listeners=[printer]).run(videos, out)
    failed = [r for r in results if not r.ok]
    print(f"\nSaida: {out.resolve()}")
    for r in results:
        mark = "OK  " if r.ok else "ERRO"
        extra = f" (falhou em {r.failed_stage}: {r.error})" if not r.ok else ""
        warn = f" | avisos: {'; '.join(r.warnings)}" if r.warnings else ""
        print(f"{mark} {r.source.name}{extra}{warn}")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="luismedia", description="LUIS MEDIA TOOLS - pos-producao de aulas com IA local")
    ap.add_argument("--version", action="version", version=f"luismedia {__version__}")
    ap.add_argument("--profile", type=Path, help="perfil YAML/JSON")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    run = sub.add_parser("run")
    run.add_argument("inputs", nargs="+", type=Path)
    run.add_argument("-o", "--out", type=Path, required=True)
    run.add_argument("--json-events", action="store_true")
    sub.add_parser("config")
    args = ap.parse_args(argv)

    try:
        settings = Settings.load(args.profile)
    except Exception as exc:  # noqa: BLE001
        print(f"Perfil invalido: {exc}", file=sys.stderr)
        return 2

    if args.cmd == "config":
        print(settings.model_dump_json(indent=2))
        return 0
    if args.cmd == "doctor":
        setup_logging()
        return cmd_doctor(settings)
    setup_logging(args.out / "job.log.jsonl")
    return cmd_run(settings, args.inputs, args.out, args.json_events)


if __name__ == "__main__":
    raise SystemExit(main())
