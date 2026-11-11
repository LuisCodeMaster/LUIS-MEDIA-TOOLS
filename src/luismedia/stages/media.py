"""Etapas de midia: extrair audio, detectar silencio, autocut, masterizar, slides, hardsub.

Funcoes puras (calculo) separadas de funcoes com efeito (ffmpeg) para poder testar
a logica sem video nenhum.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from ..adapters import ffmpeg as ff
from ..core.config import AudioConfig, AutoCutConfig, Encoder
from ..core.errors import ProcessFailed, ProcessTimeout
from ..core.logging import get_logger
from ..core.models import MediaInfo, SlideFrame, Span
from ..core.segmentation import SegmentationRules, segment_words
from ..core.style import SubtitleStyle, fonts_dir, sample_segments, write_styled_ass

log = get_logger("stages.media")


# --------------------------------------------------------------------------- audio
def extract_audio(src: MediaInfo, out: Path, *, sample_rate: int = 16_000) -> Path:
    """WAV mono 16 kHz: o formato que o Whisper espera."""
    return ff.run_to_file(
        out,
        lambda tmp: ["-i", str(src.path), "-vn", "-ac", "1", "-ar", str(sample_rate),
                     "-c:a", "pcm_s16le", str(tmp)],
        duration_hint=src.duration,
        timeout_s=max(120, src.duration * 2),
    )


_SIL_START = re.compile(r"silence_start: (-?\d+(?:\.\d+)?)")
_SIL_END = re.compile(r"silence_end: (\d+(?:\.\d+)?)")


def parse_silences(stderr: str, duration: float) -> list[Span]:
    spans, start = [], None
    for line in stderr.splitlines():
        if (m := _SIL_START.search(line)):
            start = max(0.0, float(m.group(1)))
        elif (m := _SIL_END.search(line)) and start is not None:
            spans.append(Span(start=start, end=min(duration, float(m.group(1)))))
            start = None
    if start is not None:  # silencio ate o fim do arquivo (o script antigo ignorava)
        spans.append(Span(start=start, end=duration))
    return spans


def detect_silences(audio: Path, duration: float, cfg: AutoCutConfig) -> list[Span]:
    cmd = [ff.find_binary("ffmpeg"), "-hide_banner", "-nostdin", "-i", str(audio),
           "-af", f"silencedetect=noise={cfg.noise_db}dB:d={cfg.min_silence_s}", "-f", "null", "-"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", **ff.NO_WINDOW,
                             errors="replace", timeout=max(120, duration))
    except subprocess.TimeoutExpired as exc:
        raise ProcessTimeout("silencedetect travou") from exc
    if res.returncode != 0:
        raise ProcessFailed("silencedetect falhou", returncode=res.returncode, detail=res.stderr[-2000:])
    return parse_silences(res.stderr, duration)


def speech_spans(silences: list[Span], duration: float, cfg: AutoCutConfig) -> list[Span]:
    """Inverte silencios em trechos de fala, preservando pausas longas (didaticas)."""
    cuttable = [s for s in silences if s.duration < cfg.keep_pauses_longer_than_s]
    keep: list[Span] = []
    cursor = 0.0
    for sil in cuttable:
        cut_from = min(duration, sil.start + cfg.margin_s)
        cut_to = max(cut_from, sil.end - cfg.margin_s)
        if cut_from > cursor:
            keep.append(Span(start=cursor, end=cut_from))
        cursor = max(cursor, cut_to)
    if cursor < duration:
        keep.append(Span(start=cursor, end=duration))
    return [s for s in keep if s.duration >= 0.1]


def autocut_filter(spans: list[Span]) -> str:
    """Um unico filtergraph trim+concat: 1 decodificacao, 1 codificacao, A/V em sincronia.

    O motor antigo re-codificava cada fatia em 'ultrafast' e concatenava com -c copy
    (perda de qualidade dupla e risco de estalo/dessincronia de AAC nas emendas).
    """
    parts, labels = [], []
    for i, s in enumerate(spans):
        parts.append(f"[0:v]trim=start={s.start:.3f}:end={s.end:.3f},setpts=PTS-STARTPTS[v{i}];")
        parts.append(f"[0:a]atrim=start={s.start:.3f}:end={s.end:.3f},asetpts=PTS-STARTPTS[a{i}];")
        labels.append(f"[v{i}][a{i}]")
    parts.append(f"{''.join(labels)}concat=n={len(spans)}:v=1:a=1[vout][aout]")
    return "".join(parts)


def render_autocut(src: MediaInfo, spans: list[Span], out: Path, *, encoder: Encoder,
                   crf: int, work: Path) -> Path:
    script = work / "autocut.filtergraph"
    script.write_text(autocut_filter(spans), encoding="utf-8")
    kept = sum(s.duration for s in spans)
    return ff.run_to_file(
        out,
        lambda tmp: ["-i", str(src.path), *ff.filter_script_args(script),
                     "-map", "[vout]", "-map", "[aout]", *ff.encoder_args(encoder, crf),
                     "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)],
        duration_hint=kept, timeout_s=max(600, kept * 6),
    )


def export_edl(spans: list[Span], path: Path, clip_name: str, fps: float = 30.0) -> Path:
    """EDL CMX3600 usando o fps real do video (o antigo assumia sempre 30)."""
    fps_int = max(1, round(fps))

    def tc(t: float) -> str:
        frames = round(t * fps_int)
        h, rem = divmod(frames, 3600 * fps_int)
        m, rem = divmod(rem, 60 * fps_int)
        s, f = divmod(rem, fps_int)
        return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"

    lines = ["TITLE: AUTOCUT TIMELINE", "FCM: NON-DROP FRAME", ""]
    rec = 0.0
    for i, s in enumerate(spans, start=1):
        lines += [f"{i:03d}  AX       AA/V  C        {tc(s.start)} {tc(s.end)} {tc(rec)} {tc(rec + s.duration)}",
                  f"* FROM CLIP NAME: {clip_name}", ""]
        rec += s.duration
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# --------------------------------------------------------------------- masterizacao
def master_audio(src: Path, out: Path, duration: float, cfg: AudioConfig) -> Path:
    """loudnorm em DUAS passadas (medicao + aplicacao linear): o alvo e atingido de fato.

    Uma passada so (como antes) usa modo dinamico e erra o LUFS em falas curtas.
    """
    voice = "highpass=f=80,equalizer=f=3000:width_type=o:w=2:g=3"
    target = f"I={cfg.target_lufs}:TP={cfg.true_peak_db}:LRA={cfg.lra}"
    cmd = [ff.find_binary("ffmpeg"), "-hide_banner", "-nostdin", "-i", str(src),
           "-af", f"{voice},loudnorm={target}:print_format=json", "-f", "null", "-"]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", **ff.NO_WINDOW,
                         errors="replace", timeout=max(120, duration * 2))
    if res.returncode != 0:
        raise ProcessFailed("medicao de loudness falhou", returncode=res.returncode, detail=res.stderr[-2000:])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", res.stderr, re.S)
    if not m:
        raise ProcessFailed("loudnorm nao devolveu medicao", returncode=0, detail=res.stderr[-1000:])
    meas = json.loads(m.group(0))
    second = (f"{voice},loudnorm={target}:measured_I={meas['input_i']}:measured_TP={meas['input_tp']}"
              f":measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}"
              f":offset={meas['target_offset']}:linear=true")
    return ff.run_to_file(
        out, lambda tmp: ["-i", str(src), "-af", second, "-ar", "48000", str(tmp)],
        duration_hint=duration, timeout_s=max(120, duration * 2),
    )


# --------------------------------------------------------------------------- slides
def extract_slides(src: MediaInfo, out_dir: Path, threshold: float) -> list[SlideFrame]:
    """Primeiro frame + frames de mudanca de cena, COM o timestamp real (filtro metadata).

    O editorial antigo procurava 'frame_<segundos>' no nome, mas o pipeline gerava
    '<nome>_slide_001.jpg': todo slide caia no instante 0.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    ff.run_ffmpeg(
        ["-i", str(src.path), "-vf",
         f"select='eq(n,0)+gt(scene,{threshold})',metadata=print:file=scenes.txt",
         "-fps_mode", "vfr", "-q:v", "2", "slide_%04d.jpg"],
        cwd=out_dir, duration_hint=src.duration, timeout_s=max(300, src.duration * 3),
    )
    times = [float(t) for t in re.findall(r"pts_time:(\d+(?:\.\d+)?)",
                                            (out_dir / "scenes.txt").read_text(encoding="utf-8"))]
    files = sorted(out_dir.glob("slide_*.jpg"))
    return [SlideFrame(path=f, timestamp=t) for f, t in zip(files, times, strict=False)]


# --------------------------------------------------------------------------- hardsub
def prepare_fonts(work: Path) -> str:
    """Copia as fontes embutidas (Poppins, Anton, Bebas...) para a pasta de trabalho e devolve
    o trecho do filtro. Caminho relativo: o ffmpeg roda com cwd=work."""
    dest = work / "fonts"
    if not dest.exists():
        shutil.copytree(fonts_dir(), dest)
    return ":fontsdir=fonts"


def subtitles_filter(ass_name: str, work: Path) -> str:
    return f"subtitles={ass_name}{prepare_fonts(work)}"


def render_style_preview(style: SubtitleStyle, out_png: Path, *, width: int, height: int,
                         background: Path | None = None, at: float = 1.05) -> Path:
    """Previa fiel: o proprio libass desenha a legenda de exemplo sobre um quadro do video."""
    work = out_png.parent
    work.mkdir(parents=True, exist_ok=True)
    sample = sample_segments()
    if style.max_words:  # mostra so o grupo de palavras que estaria na tela (como nos cortes)
        vertical = height > width
        rules = SegmentationRules(max_words=style.max_words, max_duration=3.0)
        sample = segment_words(sample[0].words, rules, shorts=vertical)
    write_styled_ass(sample, work / "preview.ass", style, width, height)
    scale = (f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
             "eq=brightness=-0.06")
    if background is not None:
        src = ["-ss", "1", "-i", str(background)]
    else:
        src = ["-f", "lavfi", "-i", f"gradients=s={width}x{height}:c0=0x1e293b:c1=0x4338ca:d=2"]
    # legenda aplicada ANTES do trim: o quadro escolhido mostra a legenda no instante `at`
    ff.run_ffmpeg([*src, "-vf", f"{scale},{subtitles_filter('preview.ass', work)},trim=start={at}",
                  "-frames:v", "1", str(out_png.resolve())], cwd=work, timeout_s=30, stall_timeout_s=30)
    return out_png


def burn_subtitles(src: MediaInfo, ass: Path, out: Path, *, encoder: Encoder, crf: int,
                   work: Path) -> Path:
    ff.require_filter("subtitles", "legenda queimada")
    local = work / "subs.ass"
    shutil.copyfile(ass, local)
    vf = subtitles_filter("subs.ass", work)

    def _args(tmp: Path, enc: Encoder) -> list[str]:
        return ["-i", str(src.path), "-vf", vf, *ff.encoder_args(enc, crf),
                "-c:a", "copy", "-movflags", "+faststart", str(tmp.resolve())]

    try:
        return ff.run_to_file(out, lambda t: _args(t, encoder), cwd=work,
                              duration_hint=src.duration, timeout_s=max(600, src.duration * 6))
    except (ProcessFailed, ProcessTimeout) as exc:
        if encoder is Encoder.CPU:
            raise
        log.warning("encoder de GPU falhou, refazendo na CPU",
                    extra={"encoder": encoder.value, "error": str(exc)})
        return ff.run_to_file(out, lambda t: _args(t, Encoder.CPU), cwd=work,
                              duration_hint=src.duration, timeout_s=max(600, src.duration * 8))
