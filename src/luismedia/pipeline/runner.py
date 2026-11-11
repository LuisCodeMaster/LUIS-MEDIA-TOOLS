"""Orquestrador do pipeline: substitui o Executar-MotorPipeline do PowerShell.

- Cada etapa e registrada num manifest.json (checkpoint). Se cair a luz no meio de um
  lote, rodar de novo continua de onde parou, sem refazer o que ja deu certo.
- Etapas essenciais reprovam o video; opcionais (IA, slides, cortes) so viram aviso.
  O relatorio final diz exatamente o que funcionou.
- Progresso sai como evento (callback): GUI, CLI, API ou webhook escutam o mesmo fluxo.
- Os arquivos originais do usuario nunca sao movidos nem apagados.

Estrutura de saida por video::

    <saida>/<nome>/
        <nome>_DINAMICO.mp4  <nome>_LEGENDADO.mp4  <nome>.edl
        legendas/   srt, vtt, ass, versao shorts, transcript.json
        audio/      audio bruto e masterizado
        slides/     frames + slides.json (com timestamp real)
        documentos/ Resumo-Executivo.md, Quiz-Fixacao.html, Apostila.html/.pdf
        cortes/     cortes 9:16 com legenda
        manifest.json
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import threading
import time
import zipfile
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from ..adapters import ffmpeg as ff
from ..adapters import pdf
from ..adapters.ollama import OllamaClient
from ..adapters.whisper import WhisperEngine
from ..core import subtitles
from ..core.config import Settings
from ..core.errors import LuisMediaError
from ..core.logging import get_logger
from ..core.models import MediaInfo, SlideFrame, Transcript
from ..core.segmentation import SegmentationRules, segment_transcript
from ..stages import ai, editorial, media

log = get_logger("pipeline")
Status = Literal["pending", "running", "done", "failed", "skipped"]


@dataclass
class ProgressEvent:
    video: str
    stage: str
    status: Status
    progress: float = 0.0  # 0..1 da etapa
    message: str = ""
    index: int = 0  # posicao do video no lote (1..total)
    total: int = 0


Listener = Callable[[ProgressEvent], None]


@dataclass
class VideoResult:
    source: Path
    duration: float = 0.0
    outputs: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    failed_stage: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.failed_stage is None


class Manifest:
    def __init__(self, path: Path, config_hash: str) -> None:
        self.path = path
        self.data: dict = {"config_hash": config_hash, "stages": {}}
        if path.exists():
            try:
                old = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                old = {}
            if old.get("config_hash") == config_hash:  # config mudou => refaz tudo
                self.data = old

    def done(self, stage: str) -> dict | None:
        st = self.data["stages"].get(stage)
        if st and st["status"] == "done" and all(Path(p).exists() for p in st["outputs"].values()):
            return st["outputs"]
        return None

    def record(self, stage: str, status: Status, outputs: dict[str, str] | None = None,
               error: str | None = None) -> None:
        self.data["stages"][stage] = {"status": status, "outputs": outputs or {},
                                      "error": error, "at": time.time()}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)


class Pipeline:
    def __init__(self, settings: Settings, listeners: list[Listener] | None = None,
                 cancel: threading.Event | None = None) -> None:
        self.s = settings
        self.listeners = listeners or []
        self.cancel = cancel or threading.Event()
        self.whisper = WhisperEngine(settings.whisper)
        self.encoder = ff.pick_encoder(settings.render.encoder)
        self.llm = OllamaClient(settings.llm)
        self._llm_problem: str | None | Literal["unchecked"] = "unchecked"
        self.rules = SegmentationRules(
            max_chars_line=settings.subtitles.max_chars_line,
            max_chars_shorts=settings.subtitles.max_chars_shorts,
            min_duration=settings.subtitles.min_duration_s,
            max_duration=settings.subtitles.max_duration_s,
        )
        self.config_hash = hashlib.sha256(settings.model_dump_json().encode()).hexdigest()[:16]
        self._pos = (0, 0)

    # ------------------------------------------------------------------ util
    def _emit(self, **kw) -> None:
        evt = ProgressEvent(index=self._pos[0], total=self._pos[1], **kw)
        for fn in self.listeners:
            try:
                fn(evt)
            except Exception:  # noqa: BLE001 - listener quebrado nao derruba o job
                log.exception("listener falhou")

    def _wants_llm(self) -> bool:
        c = self.s.llm
        return c.enabled and (c.summary or c.quiz or c.clips)

    def llm_problem(self) -> str | None:
        """Checa o Ollama uma vez por lote. None = pronto para uso."""
        if self._llm_problem == "unchecked":
            if not self.llm.is_running():
                self._llm_problem = f"Ollama nao esta rodando em {self.s.llm.base_url}"
            elif not self.llm.has_model():
                self._llm_problem = f"modelo {self.s.llm.model} nao baixado (ollama pull {self.s.llm.model})"
            else:
                self._llm_problem = None
        return self._llm_problem  # type: ignore[return-value]

    # ------------------------------------------------------------------ lote
    def run(self, videos: list[Path], out_root: Path) -> list[VideoResult]:
        out_root = out_root.resolve()
        out_root.mkdir(parents=True, exist_ok=True)
        results: list[VideoResult] = []
        for i, v in enumerate(videos, 1):
            if self.cancel.is_set():
                break
            self._pos = (i, len(videos))
            results.append(self.process(v.resolve(), out_root))
        self._pos = (len(videos), len(videos))
        if self.s.output.chapters and results:
            self._write_chapters(results, out_root)
        if self.s.output.zip_package and any(r.ok for r in results):
            try:
                self._zip(results, out_root)
            except OSError as exc:
                log.error("falha ao gerar ZIP", extra={"error": str(exc)})
        (out_root / "relatorio.json").write_text(json.dumps(
            [{**asdict(r), "source": str(r.source), "ok": r.ok} for r in results],
            indent=2, ensure_ascii=False), encoding="utf-8")
        return results

    def _write_chapters(self, results: list[VideoResult], out_root: Path) -> None:
        lines, acc = [], 0.0
        for r in results:
            if not r.ok:
                continue
            t = int(acc)
            stamp = f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60:02d}:{t % 60:02d}"
            lines.append(f"{stamp} - {r.source.stem}")
            acc += r.duration
        (out_root / "capitulos-youtube.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _zip(self, results: list[VideoResult], out_root: Path) -> Path:
        """ZIP64 via zipfile (sem o limite de 2 GB do Compress-Archive). Pastas nunca sao apagadas."""
        dest = out_root / "Entregavel.zip"
        tmp = dest.with_suffix(".part")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            for extra in ("capitulos-youtube.txt",):
                if (out_root / extra).exists():
                    z.write(out_root / extra, extra)
            for r in (r for r in results if r.ok):
                folder = out_root / r.source.stem
                for f in sorted(folder.rglob("*")):
                    if not f.is_file() or f.name.startswith(("manifest", "lmt_")) or "lmt_" in f.parent.name:
                        continue
                    if f.suffix.lower() in {".mp4", ".mkv", ".mov"} and not self.s.output.zip_include_videos:
                        continue
                    z.write(f, f.relative_to(out_root).as_posix())
        tmp.replace(dest)
        return dest

    # ------------------------------------------------------------------ video
    def process(self, src_path: Path, out_root: Path) -> VideoResult:
        name = src_path.stem
        out = out_root / name
        dirs = {k: out / k for k in ("legendas", "audio", "slides", "documentos", "cortes")}
        for d in dirs.values():
            d.mkdir(parents=True, exist_ok=True)
        manifest = Manifest(out / "manifest.json", self.config_hash)
        result = VideoResult(source=src_path)
        work = Path(tempfile.mkdtemp(prefix="lmt_", dir=out))

        def step(stage: str, fn: Callable[[], dict[str, str]], *, required: bool) -> bool:
            if self.cancel.is_set():
                raise LuisMediaError("cancelado pelo usuario")
            cached = manifest.done(stage)
            if cached is not None:
                result.outputs.update(cached)
                self._emit(video=name, stage=stage, status="skipped", progress=1, message="ja feito")
                return True
            self._emit(video=name, stage=stage, status="running")
            manifest.record(stage, "running")
            t0 = time.monotonic()
            try:
                outputs = fn()
            except LuisMediaError as exc:
                manifest.record(stage, "failed", error=str(exc))
                log.error("etapa falhou", extra={"video": name, "stage": stage,
                                                 "error": str(exc), "detail": exc.detail})
                self._emit(video=name, stage=stage, status="failed", message=str(exc))
                if required:
                    result.failed_stage, result.error = stage, str(exc)
                    return False
                result.warnings.append(f"{stage}: {exc}")
                return True
            manifest.record(stage, "done", outputs)
            result.outputs.update(outputs)
            log.info("etapa ok", extra={"video": name, "stage": stage,
                                        "seconds": round(time.monotonic() - t0, 1)})
            self._emit(video=name, stage=stage, status="done", progress=1)
            return True

        def skip(stage: str, why: str) -> None:
            result.warnings.append(f"{stage}: {why}")
            self._emit(video=name, stage=stage, status="skipped", message=why)

        try:
            info: MediaInfo = ff.require_audio(ff.probe(src_path))  # valida antes de gastar CPU
            target = info

            # 1. Autocut -------------------------------------------------------
            if self.s.autocut.enabled:
                def _autocut() -> dict[str, str]:
                    wav = media.extract_audio(info, work / "detect.wav")
                    spans = media.speech_spans(
                        media.detect_silences(wav, info.duration, self.s.autocut),
                        info.duration, self.s.autocut)
                    dst = out / f"{name}_DINAMICO.mp4"
                    media.render_autocut(info, spans, dst, encoder=self.encoder,
                                         crf=self.s.render.crf, work=work)
                    res = {"video_dinamico": str(dst)}
                    if self.s.autocut.export_edl:
                        res["edl"] = str(media.export_edl(spans, out / f"{name}.edl",
                                                          src_path.name, info.fps or 30))
                    return res

                if not step("autocut", _autocut, required=True):
                    return result
                target = ff.probe(Path(result.outputs["video_dinamico"]))
            result.duration = target.duration

            # 2. Audio ---------------------------------------------------------
            if not step("audio", lambda: {"audio_bruto": str(
                    media.extract_audio(target, dirs["audio"] / f"{name}.wav"))}, required=True):
                return result

            # 3. Transcricao + legendas ---------------------------------------
            def _transcribe() -> dict[str, str]:
                tr = self.whisper.transcribe(
                    Path(result.outputs["audio_bruto"]), target.duration,
                    on_progress=lambda p: self._emit(video=name, stage="transcricao",
                                                     status="running", progress=p))
                leg = dirs["legendas"]
                (leg / f"{name}.transcript.json").write_text(tr.model_dump_json(indent=2), encoding="utf-8")
                caps = segment_transcript(tr.segments, self.rules)
                res = {
                    "transcript": str(leg / f"{name}.transcript.json"),
                    "srt": str(subtitles.write_srt(caps, leg / f"{name}.srt")),
                    "vtt": str(subtitles.write_vtt(caps, leg / f"{name}.vtt")),
                    "ass": str(subtitles.write_ass(caps, leg / f"{name}.ass",
                                                   width=target.width or 1920,
                                                   height=target.height or 1080)),
                }
                if self.s.subtitles.shorts_version:
                    shorts = segment_transcript(tr.segments, self.rules, shorts=True)
                    res["srt_shorts"] = str(subtitles.write_srt(shorts, leg / f"{name}_shorts.srt"))
                return res

            if not step("transcricao", _transcribe, required=True):
                return result
            transcript = Transcript.model_validate_json(
                Path(result.outputs["transcript"]).read_text(encoding="utf-8"))

            # 4. Audio master + hardsub ---------------------------------------
            if self.s.audio.master:
                step("masterizacao", lambda: {"audio_master": str(media.master_audio(
                    Path(result.outputs["audio_bruto"]), dirs["audio"] / f"{name}_master.wav",
                    target.duration, self.s.audio))}, required=False)

            if self.s.render.hardsub:
                step("hardsub", lambda: {"video_legendado": str(media.burn_subtitles(
                    target, Path(result.outputs["ass"]), out / f"{name}_LEGENDADO.mp4",
                    encoder=self.encoder, crf=self.s.render.crf, work=work))}, required=False)

            # 5. IA -----------------------------------------------------------
            summary_md: str | None = None
            if self._wants_llm():
                problem = self.llm_problem()
                if problem:
                    skip("ia", problem)
                else:
                    self._ai_steps(step, name, target, transcript, dirs)
                    sp = result.outputs.get("resumo")
                    summary_md = Path(sp).read_text(encoding="utf-8") if sp else None

            # 6. Slides + apostila --------------------------------------------
            if self.s.slides.enabled:
                def _slides() -> dict[str, str]:
                    frames = media.extract_slides(target, dirs["slides"], self.s.slides.scene_threshold)
                    idx = dirs["slides"] / "slides.json"
                    idx.write_text(json.dumps([f.model_dump(mode="json") for f in frames], indent=2),
                                   encoding="utf-8")
                    return {"slides_index": str(idx)}

                step("slides", _slides, required=False)

            if self.s.slides.handout:
                def _handout() -> dict[str, str]:
                    frames: list[SlideFrame] = []
                    if "slides_index" in result.outputs:
                        frames = [SlideFrame.model_validate(x) for x in json.loads(
                            Path(result.outputs["slides_index"]).read_text(encoding="utf-8"))]
                    page = editorial.build_handout(name, frames, transcript,
                                                   dirs["documentos"] / "Apostila.html", summary_md)
                    res = {"apostila_html": str(page)}
                    if self.s.slides.handout_pdf:
                        try:
                            res["apostila_pdf"] = str(pdf.html_to_pdf(page, dirs["documentos"] / "Apostila.pdf"))
                        except LuisMediaError as exc:
                            result.warnings.append(f"apostila_pdf: {exc}")
                    return res

                step("apostila", _handout, required=False)
            return result
        except LuisMediaError as exc:  # probe/validacao/cancelamento
            result.failed_stage, result.error = result.failed_stage or "validacao", str(exc)
            self._emit(video=name, stage=result.failed_stage, status="failed", message=str(exc))
            return result
        finally:
            if not self.s.keep_intermediates:
                shutil.rmtree(work, ignore_errors=True)

    def _ai_steps(self, step, name: str, target: MediaInfo, tr: Transcript, dirs: dict[str, Path]) -> None:
        c = self.s.llm
        material: dict[str, str] = {}

        def _material() -> str:
            if "m" not in material:
                material["m"] = ai.condensed_text(self.llm, tr, c.max_context_chars)
            return material["m"]

        if c.summary:
            def _summary() -> dict[str, str]:
                p = dirs["documentos"] / "Resumo-Executivo.md"
                p.write_text(ai.summary(self.llm, _material(), name), encoding="utf-8")
                return {"resumo": str(p)}
            step("resumo", _summary, required=False)

        if c.quiz:
            def _quiz() -> dict[str, str]:
                p = dirs["documentos"] / "Quiz-Fixacao.html"
                p.write_text(ai.quiz_html(ai.quiz(self.llm, _material()), name, seed=name), encoding="utf-8")
                return {"quiz": str(p)}
            step("quiz", _quiz, required=False)

        if c.clips:
            def _clips() -> dict[str, str]:
                plan = ai.pick_clips(self.llm, tr, c.clips_count, c.max_context_chars)
                res = {}
                for i, clip in enumerate(plan, 1):
                    slug = "".join(ch if ch.isalnum() else "_" for ch in clip.title)[:50].strip("_")
                    dst = dirs["cortes"] / f"{name}_corte_{i}_{slug or 'trecho'}.mp4"
                    ai.render_vertical_clip(target, clip, tr, dst, encoder=self.encoder,
                                            crf=self.s.render.crf, rules=self.rules)
                    res[f"corte_{i}"] = str(dst)
                return res
            step("cortes", _clips, required=False)
