"""Orquestrador do pipeline: substitui o Executar-MotorPipeline do PowerShell.

- Cada etapa e registrada num manifest.json (checkpoint). Se cair a luz no meio de um
  lote, rodar de novo continua de onde parou, sem refazer o que ja deu certo.
- Etapas essenciais reprovam o video; opcionais (IA, slides, cortes) so viram aviso.
  O relatorio final diz exatamente o que funcionou.
- Progresso sai como evento (callback): GUI, CLI, API ou webhook escutam o mesmo fluxo.
- Os arquivos originais do usuario nunca sao movidos nem apagados.

Estrutura de saida por video::

    <saida>/<nome>/
        <nome>_EDITADO.mp4 (sem pausas/vicios)  <nome>_LEGENDADO.mp4  <nome>_edicao.edl
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
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Literal

from ..adapters import ffmpeg as ff
from ..adapters import pdf
from ..adapters.ollama import OllamaClient
from ..adapters.whisper import WhisperEngine
from ..core import cleanup, report, subtitles
from ..core.captions import CaptionDoc, apply_to_doc, realign_words
from ..core.config import Settings
from ..core.errors import Cancelled, LuisMediaError
from ..core.logging import get_logger
from ..core.models import MediaInfo, SlideFrame, Transcript, Word
from ..core.segmentation import SegmentationRules, segment_transcript, segment_words
from ..core.style import emoji_plan, write_styled_ass
from ..core.sync import rules_for_pace, snap, speech_regions
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
    needs_review: bool = False  # parou para revisao das legendas (nao e falha)

    @property
    def ok(self) -> bool:
        return self.failed_stage is None


# Quais etapas precisam ser refeitas quando outra roda de novo
DEPENDS: dict[str, list[str]] = {
    "autocut": [], "audio": ["autocut"], "transcricao": ["audio"], "masterizacao": ["audio"],
    "palavras-chave": ["transcricao"], "limpeza": ["transcricao"], "edicao": ["limpeza"],
    "legendas": ["transcricao", "palavras-chave", "edicao"], "hardsub": ["legendas"], "resumo": ["transcricao"],
    "quiz": ["transcricao"], "cortes": ["legendas"], "slides": ["autocut", "edicao"],
    "apostila": ["slides", "legendas", "resumo"], "relatorio": ["edicao"],
}
# Etapas que dependem do texto das legendas (refeitas quando o usuario edita no app)
# (os cortes de pausas/vicios ficam no mesmo arquivo, entao a edicao do video tambem e refeita)
CAPTION_STAGES = ["edicao", "legendas"]


def stage_config(settings: Settings, stage: str) -> str:
    """Hash so da parte da configuracao que afeta a etapa: mudar o estilo da legenda nao
    refaz a transcricao, mudar o modelo do Whisper refaz so dali para frente."""
    s = settings
    parts = {
        "autocut": [s.autocut, s.render.crf],
        "audio": [],
        "transcricao": [s.whisper, s.subtitles.model_dump(exclude={"style_h", "style_v", "review",
                                                                   "shorts_version", "pace", "snap_to_speech"}),
                        s.cleanup.enabled and s.cleanup.fillers],
        "limpeza": [s.cleanup.detection()],
        "edicao": [s.render.crf, s.cleanup.enabled, s.cleanup.export_edl],
        "masterizacao": [s.audio],
        "palavras-chave": [s.llm.model],
        "legendas": [s.subtitles.style_h, s.subtitles.shorts_version, s.subtitles.max_chars_shorts,
                     s.whisper.vocabulary],
        "hardsub": [s.render],
        "resumo": [s.llm.model, s.llm.max_context_chars],
        "quiz": [s.llm.model, s.llm.max_context_chars],
        "cortes": [s.llm.model, s.llm.clips_count, s.subtitles.style_v, s.render.crf],
        "slides": [s.slides.scene_threshold],
        "apostila": [s.slides.handout_pdf],
        "relatorio": [s.llm.enabled, s.llm.model, s.subtitles.max_cps],
    }.get(stage, [])
    raw = json.dumps([p.model_dump(mode="json") if hasattr(p, "model_dump") else p for p in parts],
                     sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def sync_marker(wav: Path) -> Path:
    """Arquivo ao lado do WAV dizendo que ele ja foi extraido alinhado com a imagem."""
    return wav.with_name(wav.name + ".sync")


def repair_av_offset(target: MediaInfo, out_dir: Path, name: str) -> float:
    """Conserta resultados das versoes ate 1.5.0, que extraiam o audio sem o atraso inicial
    (legendas adiantadas pelo mesmo tanto). Reextrai o WAV alinhado e empurra legendas,
    cortes e transcricao. Roda uma vez por video; devolve o atraso corrigido (0 se nada)."""
    from ..core.sync import shift_all

    wav = out_dir / "audio" / f"{name}.wav"
    marker = sync_marker(wav)
    if marker.exists() or not wav.exists():
        return 0.0
    off = target.audio_offset
    leg = out_dir / "legendas"
    capp = leg / f"{name}.captions.json"
    doc = CaptionDoc.load(capp) if capp.exists() else None
    if off > 0.02:
        media.extract_audio(target, wav)
        if doc is not None and doc.av_offset is None:
            dur = doc.duration or target.duration
            doc.captions = shift_all(doc.captions, off)
            doc.cuts = [c.model_copy(update={"start": min(c.start + off, dur - 0.06),
                                             "end": min(c.end + off, dur)}) for c in doc.cuts
                        if c.start + off < dur - 0.06]
            trp = leg / f"{name}.transcript.json"
            if trp.exists():
                tr = Transcript.model_validate_json(trp.read_text(encoding="utf-8"))
                tr.segments = shift_all(tr.segments, off)
                trp.write_text(tr.model_dump_json(indent=2), encoding="utf-8")
        envp = out_dir / "audio" / f"{name}.envelope.json"
        if envp.exists():
            try:
                envp.write_text(json.dumps({"rate": 50, "rms": cleanup.read_envelope_wav(wav)}), encoding="utf-8")
            except (ImportError, OSError, EOFError):
                envp.unlink(missing_ok=True)
    if doc is not None and doc.av_offset is None:
        doc.av_offset = off
        doc.save(capp)
        if off > 0.02:
            captions_edited(out_dir)  # legendas/videos ja gerados com o tempo antigo
    marker.write_text(str(off), encoding="utf-8")
    return off if off > 0.02 else 0.0


def caption_rules(settings: Settings) -> SegmentationRules:
    """Regras de montagem das legendas (16:9) a partir das configuracoes, ja com o ritmo."""
    sub = settings.subtitles
    return rules_for_pace(SegmentationRules(
        max_chars_line=sub.max_chars_line, max_chars_shorts=sub.max_chars_shorts,
        min_duration=sub.min_duration_s, max_duration=sub.max_duration_s,
        gap=sub.min_gap_s, max_cps=sub.max_cps, max_words=sub.style_h.max_words,
    ), sub.pace)


class Manifest:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict = {"version": 2, "stages": {}}
        if path.exists():
            try:
                old = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                old = {}
            if old.get("version") == 2:
                self.data = old

    def done(self, stage: str, cfg: str) -> dict | None:
        st = self.data["stages"].get(stage)
        if (st and st["status"] == "done" and st.get("cfg") == cfg
                and all(Path(p).exists() for p in st["outputs"].values())):
            return st["outputs"]
        return None

    def record(self, stage: str, status: Status, outputs: dict[str, str] | None = None,
               error: str | None = None, cfg: str = "") -> None:
        self.data["stages"][stage] = {"status": status, "outputs": outputs or {},
                                      "error": error, "cfg": cfg, "at": time.time()}
        self._save()

    def invalidate(self, stages: list[str]) -> None:
        for st in stages:
            self.data["stages"].pop(st, None)
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)


def captions_edited(out_dir: Path) -> None:
    """Chamado pelo editor do app: o texto mudou, refaz legendas e tudo que depende delas."""
    Manifest(out_dir / "manifest.json").invalidate(CAPTION_STAGES)


def find_reviews(out_root: Path) -> list[Path]:
    """Legendas de um lote (para o editor do app): caminhos dos <nome>.captions.json."""
    return sorted(out_root.glob("*/legendas/*.captions.json"))


class Pipeline:
    def __init__(self, settings: Settings, listeners: list[Listener] | None = None,
                 cancel: threading.Event | None = None) -> None:
        self.s = settings
        self.listeners = listeners or []
        self.cancel = cancel or threading.Event()
        self.whisper = WhisperEngine(settings.whisper,
                                     fillers=settings.cleanup.enabled and settings.cleanup.fillers)
        self.whisper.cancel = self.cancel
        self.encoder = ff.pick_encoder(settings.render.encoder)
        self.llm = OllamaClient(settings.llm)
        self._llm_problem: str | None | Literal["unchecked"] = "unchecked"
        sub = settings.subtitles
        self.rules = caption_rules(settings)
        self.rules_v = replace(self.rules, max_words=sub.style_v.max_words, max_duration=min(sub.max_duration_s, 3.0))
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
        ff.set_cancel_event(self.cancel)
        try:
            return self._run(videos, out_root)
        finally:
            ff.set_cancel_event(None)

    def _run(self, videos: list[Path], out_root: Path) -> list[VideoResult]:
        out_root = out_root.resolve()
        out_root.mkdir(parents=True, exist_ok=True)
        results: list[VideoResult] = []
        for i, v in enumerate(videos, 1):
            if self.cancel.is_set():
                break
            self._pos = (i, len(videos))
            results.append(self.process(v.resolve(), out_root))
        self._pos = (len(videos), len(videos))
        finished = [r for r in results if r.ok and not r.needs_review]
        if self.s.output.chapters and finished:
            self._write_chapters(finished, out_root)
        if self.s.output.zip_package and finished:
            try:
                self._zip(finished, out_root)
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
        manifest = Manifest(out / "manifest.json")
        result = VideoResult(source=src_path)
        work = Path(tempfile.mkdtemp(prefix="lmt_", dir=out))
        rerun: set[str] = set()  # etapas executadas agora (forcam as dependentes)

        def step(stage: str, fn: Callable[[], dict[str, str]], *, required: bool) -> bool:
            if self.cancel.is_set():
                raise Cancelled("cancelado pelo usuario")
            cfg = stage_config(self.s, stage)
            cached = None if any(d in rerun for d in DEPENDS.get(stage, [])) else manifest.done(stage, cfg)
            if cached is not None:
                result.outputs.update(cached)
                self._emit(video=name, stage=stage, status="skipped", progress=1, message="ja feito")
                return True
            rerun.add(stage)
            self._emit(video=name, stage=stage, status="running")
            manifest.record(stage, "running", cfg=cfg)
            t0 = time.monotonic()
            try:
                outputs = fn()
            except Cancelled:
                manifest.record(stage, "failed", error="cancelado", cfg=cfg)
                raise
            except Exception as exc:  # noqa: BLE001 - nenhum erro derruba o lote inteiro
                if not isinstance(exc, LuisMediaError):
                    log.exception("erro inesperado", extra={"video": name, "stage": stage})
                    exc = LuisMediaError(f"erro inesperado: {exc}", detail=repr(exc))
                manifest.record(stage, "failed", error=str(exc), cfg=cfg)
                log.error("etapa falhou", extra={"video": name, "stage": stage,
                                                 "error": str(exc), "detail": exc.detail})
                self._emit(video=name, stage=stage, status="failed", message=str(exc))
                if required:
                    result.failed_stage, result.error = stage, str(exc)
                    return False
                result.warnings.append(f"{stage}: {exc}")
                return True
            manifest.record(stage, "done", outputs, cfg=cfg)
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
            result.outputs["video_base"] = str(target.path)

            # 2. Audio ---------------------------------------------------------
            def _audio() -> dict[str, str]:
                wav = media.extract_audio(target, dirs["audio"] / f"{name}.wav")
                sync_marker(wav).write_text(str(target.audio_offset), encoding="utf-8")
                return {"audio_bruto": str(wav)}

            if not step("audio", _audio, required=True):
                return result
            fixed = repair_av_offset(target, out, name)  # resultados de versoes antigas
            if fixed:
                log.info("atraso do audio corrigido", extra={"video": name, "offset_s": fixed})

            # 3. Transcricao + legenda editavel ------------------------------
            def _transcribe() -> dict[str, str]:
                tr = self.whisper.transcribe(
                    Path(result.outputs["audio_bruto"]), target.duration,
                    on_progress=lambda p: self._emit(video=name, stage="transcricao",
                                                     status="running", progress=p))
                leg = dirs["legendas"]
                (leg / f"{name}.transcript.json").write_text(tr.model_dump_json(indent=2), encoding="utf-8")
                caps = segment_transcript(tr.segments, self.rules)
                res: dict[str, str] = {}
                wav = Path(result.outputs["audio_bruto"])
                env: list[float] | None = None
                regions: list = []
                synced = False
                try:  # volume do audio: checagem de pausas e onda da linha do tempo
                    env = cleanup.read_envelope_wav(wav)
                    envp = dirs["audio"] / f"{name}.envelope.json"
                    envp.write_text(json.dumps({"rate": 50, "rms": env}), encoding="utf-8")
                    res["envelope"] = str(envp)
                except (ImportError, OSError, EOFError) as exc:
                    log.warning("sem envelope de audio", extra={"error": str(exc)})
                try:  # detector de voz: onde a fala comeca de verdade (funciona com musica de fundo)
                    from ..adapters.whisper import load_audio

                    regions = speech_regions(load_audio(wav))
                    if regions:
                        sp = dirs["audio"] / f"{name}.speech.json"
                        sp.write_text(json.dumps({"regions": regions}), encoding="utf-8")
                        res["voz"] = str(sp)
                except Exception as exc:  # noqa: BLE001 - sem detector, encaixa pelo volume
                    log.warning("detector de voz indisponivel", extra={"error": str(exc)})
                if self.s.subtitles.snap_to_speech and (regions or env):
                    caps = snap(caps, regions, env)
                    synced = True
                doc = CaptionDoc(video=str(target.path), width=target.width or 1920,
                                 height=target.height or 1080, duration=target.duration, captions=caps,
                                 pace=self.s.subtitles.pace, av_offset=target.audio_offset, voice_sync=synced)
                apply_to_doc(doc, self.s.subtitles.replacements)
                return {"transcript": str(leg / f"{name}.transcript.json"),
                        "captions": str(doc.save(leg / f"{name}.captions.json")), **res}

            if not step("transcricao", _transcribe, required=True):
                return result
            captions_path = Path(result.outputs["captions"])

            # 3b. Pausas e vicios (sugestoes revisaveis; o corte so acontece no passo 7)
            if self.s.cleanup.enabled:
                def _clean() -> dict[str, str]:
                    env: list[float] | None = None
                    envp = dirs["audio"] / f"{name}.envelope.json"
                    try:
                        if envp.exists():
                            env = json.loads(envp.read_text(encoding="utf-8"))["rms"]
                        else:
                            env = cleanup.read_envelope_wav(Path(result.outputs["audio_bruto"]))
                            envp.write_text(json.dumps({"rate": 50, "rms": env}), encoding="utf-8")
                    except (ImportError, OSError, EOFError, ValueError, KeyError) as exc:
                        log.warning("sem envelope de audio", extra={"error": str(exc)})
                    d = CaptionDoc.load(captions_path)
                    found = cleanup.detect_cuts(d.captions, target.duration, self.s.cleanup.detection(), env)
                    d.cuts = cleanup.merge_detected(d.cuts, found)
                    d.duration = target.duration
                    d.save(captions_path)
                    on = [c for c in found if c.enabled]
                    p = dirs["legendas"] / f"{name}.cortes.json"
                    p.write_text(json.dumps({"sugeridos": len(found), "marcados": len(on),
                                             "segundos": round(cleanup.removed_seconds(on), 1)}), encoding="utf-8")
                    return {"limpeza": str(p), **({"envelope": str(envp)} if env else {})}
                step("limpeza", _clean, required=False)

            # 4. Audio master (nao depende do texto) -------------------------
            if self.s.audio.master:
                step("masterizacao", lambda: {"audio_master": str(media.master_audio(
                    Path(result.outputs["audio_bruto"]), dirs["audio"] / f"{name}_master.wav",
                    target.duration, self.s.audio))}, required=False)

            # 5. IA de texto (resumo/quiz usam a transcricao) ----------------
            transcript = Transcript.model_validate_json(
                Path(result.outputs["transcript"]).read_text(encoding="utf-8"))
            llm_ok = False
            if self._wants_llm():
                problem = self.llm_problem()
                if problem:
                    skip("ia", problem)
                else:
                    llm_ok = True
                    self._text_ai(step, name, transcript, dirs)
                    if self.s.subtitles.style_h.keywords or self.s.subtitles.style_v.keywords:
                        def _keywords() -> dict[str, str]:
                            kws = ai.keywords(self.llm, transcript.plain_text(), self.s.llm.max_context_chars)
                            d = CaptionDoc.load(captions_path)
                            if not d.keywords:  # nao sobrescreve o que o usuario editou
                                d.keywords = kws
                                d.save(captions_path)
                            p = dirs["legendas"] / f"{name}.keywords.json"
                            p.write_text(json.dumps(kws, ensure_ascii=False), encoding="utf-8")
                            return {"keywords": str(p)}
                        step("palavras-chave", _keywords, required=False)

            # 6. Revisao: para aqui ate o usuario aprovar no app -------------
            doc = CaptionDoc.load(captions_path)
            if self.s.subtitles.review and not doc.approved:
                result.needs_review = True
                self._emit(video=name, stage="revisao", status="skipped",
                           message="aguardando revisao das legendas")
                return result

            # 7. Edicao: aplica os cortes aprovados (pausas, vicios, cortes manuais) --------
            def _edit() -> dict[str, str]:
                cuts = self._active_cuts(CaptionDoc.load(captions_path))
                if not cuts:
                    return {}
                spans = cleanup.kept_spans(cuts, target.duration)
                dst = out / f"{name}_EDITADO.mp4"
                media.render_autocut(target, spans, dst, encoder=self.encoder, crf=self.s.render.crf, work=work)
                res = {"video_editado": str(dst)}
                if self.s.cleanup.export_edl:
                    res["edl_edicao"] = str(media.export_edl(spans, out / f"{name}_edicao.edl",
                                                             target.path.name, target.fps or 30))
                return res

            original = target
            if not step("edicao", _edit, required=True):
                return result
            if "video_editado" in result.outputs:
                target = ff.probe(Path(result.outputs["video_editado"]))
                result.duration = target.duration
                result.outputs["video_base"] = str(target.path)
            time_map = cleanup.TimeMap(self._active_cuts(CaptionDoc.load(captions_path)))

            # 7b. Relatorio do professor (ritmo, vicios, regravacoes, dicas) ---------------
            if self.s.output.teacher_report:
                def _report() -> dict[str, str]:
                    d = CaptionDoc.load(captions_path)
                    cuts = [c for c in d.cuts if self.s.cleanup.enabled or c.kind in cleanup.USER_KINDS]
                    r = report.build_report(d.captions, cuts, d.duration or original.duration,
                                            self.s.subtitles.max_cps)
                    tips = report.auto_tips(r)
                    if llm_ok:
                        stats = json.dumps({k: r[k] for k in ("wpm", "fillers", "crutches", "retakes", "questions",
                                                              "longest_run", "fast", "scores")},
                                           ensure_ascii=False, default=str)[:3000]
                        text = " ".join(c.text.replace("\n", " ") for c in d.captions)
                        try:
                            tips = ai.teacher_tips(self.llm, stats, text, self.s.llm.max_context_chars) + tips[:2]
                        except Exception as exc:  # noqa: BLE001 - sem IA o relatorio sai com as dicas automaticas
                            log.warning("dicas da IA falharam", extra={"error": str(exc)})
                    r["tips"] = tips
                    doc_dir = dirs["documentos"]
                    (doc_dir / "relatorio-professor.json").write_text(
                        json.dumps(r, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
                    page = doc_dir / "Relatorio-do-Professor.html"
                    page.write_text(report.render_html(r, name), encoding="utf-8")
                    return {"relatorio_professor": str(page), "relatorio_professor_json":
                            str(doc_dir / "relatorio-professor.json")}
                step("relatorio", _report, required=False)

            # 8. Arquivos de legenda (do texto revisado, no tempo do video editado) ----
            def _subs() -> dict[str, str]:
                d = self._edited_doc(captions_path)
                leg = dirs["legendas"]
                res = {
                    "srt": str(subtitles.write_srt(d.captions, leg / f"{name}.srt")),
                    "vtt": str(subtitles.write_vtt(d.captions, leg / f"{name}.vtt")),
                    "ass": str(write_styled_ass(d.captions, leg / f"{name}.ass", self.s.subtitles.style_h,
                                                d.width, d.height, keywords=self._keywords(d))),
                }
                if self.s.subtitles.shorts_version:
                    shorts = segment_words(caption_words(d), self.rules, shorts=True)
                    res["srt_shorts"] = str(subtitles.write_srt(shorts, leg / f"{name}_shorts.srt"))
                return res

            if not step("legendas", _subs, required=True):
                return result

            if self.s.render.hardsub:
                def _hardsub() -> dict[str, str]:
                    d = self._edited_doc(captions_path)
                    emojis = emoji_plan(d.captions, self.s.subtitles.style_h, d.width, d.height, self._keywords(d))
                    return {"video_legendado": str(media.burn_subtitles(
                        target, Path(result.outputs["ass"]), out / f"{name}_LEGENDADO.mp4",
                        encoder=self.encoder, crf=self.s.render.crf, work=work, emojis=emojis))}
                step("hardsub", _hardsub, required=False)

            # 9. Cortes 9:16 (do texto revisado, com o estilo vertical) ------
            if llm_ok and self.s.llm.clips:
                def _clips() -> dict[str, str]:
                    d = self._edited_doc(captions_path)
                    plan = ai.pick_clips(self.llm, transcript, self.s.llm.clips_count, self.s.llm.max_context_chars)
                    # a IA escolhe no tempo original; o corte sai do video ja editado
                    plan = [c.model_copy(update={"start": time_map(c.start), "end": time_map(c.end)}) for c in plan]
                    res = {}
                    for i, clip in enumerate(plan, 1):
                        slug = "".join(ch if ch.isalnum() else "_" for ch in clip.title)[:50].strip("_")
                        dst = dirs["cortes"] / f"{name}_corte_{i}_{slug or 'trecho'}.mp4"
                        ai.render_vertical_clip(target, clip, d.captions, dst, encoder=self.encoder,
                                                crf=self.s.render.crf, rules=self.rules_v,
                                                style=self.s.subtitles.style_v, keywords=self._keywords(d))
                        res[f"corte_{i}"] = str(dst)
                    return res
                step("cortes", _clips, required=False)

            # 10. Slides + apostila -------------------------------------------
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
                    sp = result.outputs.get("resumo")
                    summary_md = Path(sp).read_text(encoding="utf-8") if sp and Path(sp).exists() else None
                    d = self._edited_doc(captions_path)
                    tr = Transcript(language=transcript.language, duration=transcript.duration,
                                    model=transcript.model, device=transcript.device,
                                    segments=[c.model_copy(update={"text": c.text.replace("\n", " ")})
                                              for c in d.captions])
                    page = editorial.build_handout(name, frames, tr, dirs["documentos"] / "Apostila.html", summary_md)
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

    def _active_cuts(self, doc: CaptionDoc) -> list[cleanup.Cut]:
        """Cortes ligados. Com a limpeza desligada, so os cortes manuais feitos no app."""
        return [c for c in doc.cuts if c.enabled and (self.s.cleanup.enabled or c.kind in cleanup.USER_KINDS)]

    def _edited_doc(self, path: Path) -> CaptionDoc:
        """Legendas no tempo do video editado (sem as palavras cortadas)."""
        d = CaptionDoc.load(path)
        cuts = self._active_cuts(d)
        if cuts:
            d = d.model_copy(update={"captions": cleanup.remap_captions(
                d.captions, cuts, self.s.subtitles.max_chars_line)})
        return d

    def _keywords(self, doc: CaptionDoc) -> list[str]:
        """Palavras-chave da legenda (IA ou editadas) + vocabulario da aula."""
        return list(dict.fromkeys([*doc.keywords, *self.s.whisper.vocabulary]))

    def _text_ai(self, step, name: str, tr: Transcript, dirs: dict[str, Path]) -> None:
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


def caption_words(doc: CaptionDoc) -> list[Word]:
    """Palavras com tempo de todas as legendas (ja com as correcoes do usuario)."""
    return [w for c in doc.captions for w in (c.words or realign_words(c, c.text.replace("\n", " ")).words)]
