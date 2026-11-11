"""Escrita de SRT/VTT/ASS com timecode em milissegundos inteiros.

Corrige o bug do pipeline antigo: f"{s:06.3f}" com s=59.9996 gera "00:00:60,000",
timecode invalido que alguns players rejeitam.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .models import Segment


def _split_ms(seconds: float) -> tuple[int, int, int, int]:
    total_ms = max(0, round(seconds * 1000))
    h, rem = divmod(total_ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return h, m, s, ms


def srt_time(seconds: float) -> str:
    h, m, s, ms = _split_ms(seconds)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def vtt_time(seconds: float) -> str:
    return srt_time(seconds).replace(",", ".")


def ass_time(seconds: float) -> str:
    total_cs = max(0, round(seconds * 100))
    h, rem = divmod(total_cs, 360_000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _clean(text: str) -> str:
    """Normaliza espacos mas preserva a quebra de linha feita pela segmentacao."""
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def write_srt(segments: Iterable[Segment], path: Path) -> Path:
    lines: list[str] = []
    for i, seg in enumerate((s for s in segments if _clean(s.text)), start=1):
        lines += [str(i), f"{srt_time(seg.start)} --> {srt_time(seg.end)}", _clean(seg.text), ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_vtt(segments: Iterable[Segment], path: Path) -> Path:
    lines = ["WEBVTT", ""]
    for seg in segments:
        if _clean(seg.text):
            lines += [f"{vtt_time(seg.start)} --> {vtt_time(seg.end)}", _clean(seg.text), ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: AulaFluida,Arial,{font},&H00FFFFFF,&H0000FFFF,&H00000000,&H60000000,{bold},0,0,0,100,100,0,0,1,{outline},1,2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def write_ass(segments: Iterable[Segment], path: Path, *, width: int = 1920, height: int = 1080,
              vertical: bool = False) -> Path:
    if vertical:  # 9:16: letra maior, em negrito, acima da interface do app
        font, bold, outline, margin_v = round(width * 0.06), -1, 3, round(height * 0.18)
    else:  # 16:9: escala com a resolucao real do video
        font, bold, outline, margin_v = round(54 * height / 1080), 0, 1.5, round(35 * height / 1080)
    out = [ASS_HEADER.format(w=width, h=height, font=font, bold=bold, outline=outline, margin_v=margin_v)]
    for seg in segments:
        text = _clean(seg.text).replace("{", "(").replace("}", ")")  # chaves sao tags no ASS
        text = text.replace("\n", "\\N")
        if text:
            out.append(
                f"Dialogue: 0,{ass_time(seg.start)},{ass_time(seg.end)},AulaFluida,,0,0,0,,"
                f"{{\\fad(150,150)}}{text}\n"
            )
    path.write_text("".join(out), encoding="utf-8")
    return path
