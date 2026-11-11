"""Estilos de legenda (estilo CapCut) e geracao do arquivo ASS.

Um estilo descreve fonte, cores, contorno, caixa de fundo, posicao, animacao de entrada e
destaque da palavra falada (karaoke). O mesmo ASS e usado na legenda queimada, nos cortes
9:16 e na previa da tela de estilos: o que se ve na previa e exatamente o que sai no video.

Tamanhos sao relativos ao lado menor do video (5 = 5%), entao o estilo funciona igual em
1080p, 4K ou 9:16.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from importlib import resources
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import Segment, Word

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
Position = Literal["bottom", "middle", "top"]
Animation = Literal["none", "fade", "pop"]
Highlight = Literal["none", "color", "pop", "reveal"]

BUNDLED_FONTS = ["Poppins", "Poppins ExtraBold", "Poppins Black", "Anton", "Bebas Neue", "Archivo Black"]
SYSTEM_FONTS = ["Arial", "Segoe UI", "Verdana", "Impact", "Calibri", "Georgia"]


def fonts_dir() -> Path:
    return Path(str(resources.files("luismedia") / "assets" / "fonts"))


class SubtitleStyle(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    font: str = "Arial"
    size: float = Field(5.0, ge=2, le=15)            # % do lado menor do video
    bold: bool = False
    italic: bool = False
    uppercase: bool = False
    color: str = "#FFFFFF"
    outline_color: str = "#000000"
    outline: float = Field(1.5, ge=0, le=12)        # px na referencia 1080
    shadow: float = Field(1.0, ge=0, le=10)
    glow: float = Field(0.0, ge=0, le=10)            # desfoque do contorno (efeito neon)
    box: bool = False
    box_color: str = "#000000"
    box_opacity: float = Field(0.6, ge=0, le=1)
    position: Position = "bottom"
    margin: float = Field(3.2, ge=0, le=45)          # % da altura, a partir da borda
    animation: Animation = "fade"
    highlight: Highlight = "none"
    highlight_color: str = "#FFE600"
    max_words: int = Field(0, ge=0, le=12)           # 0 = automatico (pelo tamanho da linha)

    @field_validator("color", "outline_color", "box_color", "highlight_color")
    @classmethod
    def _hex(cls, v: str) -> str:
        if not HEX.match(v):
            raise ValueError(f"cor invalida: {v} (use #RRGGBB)")
        return v.upper()


PRESETS_H: dict[str, SubtitleStyle] = {
    "Clássico (aula)": SubtitleStyle(),
    "Caixa escura": SubtitleStyle(font="Segoe UI", bold=True, outline=0.5, shadow=0, box=True,
                                  box_opacity=0.65, animation="fade"),
    "Amarelo TV": SubtitleStyle(font="Arial", bold=True, color="#FFE600", outline=2.5, shadow=1.5),
    "Moderno": SubtitleStyle(font="Poppins", bold=True, size=4.8, outline=2.0, shadow=0,
                             highlight="color", highlight_color="#7DD3FC", animation="none"),
}

PRESETS_V: dict[str, SubtitleStyle] = {
    "CapCut amarelo": SubtitleStyle(font="Poppins Black", size=8.5, uppercase=True, outline=4.0, shadow=1.5,
                                    position="bottom", margin=28, animation="pop", highlight="pop",
                                    highlight_color="#FFE600", max_words=3),
    "Destaque verde": SubtitleStyle(font="Anton", size=10.0, uppercase=True, outline=4.5, shadow=0,
                                    position="middle", animation="pop", highlight="color",
                                    highlight_color="#39FF14", max_words=2),
    "Karaokê": SubtitleStyle(font="Bebas Neue", size=10.5, uppercase=True, outline=3.0, shadow=2,
                             position="bottom", margin=24, animation="none", highlight="reveal", max_words=4),
    "Caixa minimal": SubtitleStyle(font="Poppins", bold=True, size=6.5, outline=0, shadow=0, box=True,
                                   box_opacity=0.75, position="bottom", margin=22, animation="fade", max_words=5),
    "Neon": SubtitleStyle(font="Archivo Black", size=8.0, uppercase=True, color="#FFFFFF",
                          outline_color="#E11DFF", outline=3.5, glow=4, shadow=0, position="middle",
                          animation="pop", highlight="color", highlight_color="#22D3EE", max_words=3),
}


def ass_color(hex_rgb: str, opacity: float = 1.0) -> str:
    """#RRGGBB -> &HAABBGGRR (no ASS o alfa e invertido: 00 = opaco)."""
    r, g, b = hex_rgb[1:3], hex_rgb[3:5], hex_rgb[5:7]
    alpha = round((1 - opacity) * 255)
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def _ass_time(seconds: float) -> str:
    total_cs = max(0, round(seconds * 100))
    h, rem = divmod(total_cs, 360_000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def header(style: SubtitleStyle, width: int, height: int) -> str:
    base = min(width, height)
    k = base / 1080  # contorno/sombra definidos na referencia 1080
    font_px = round(base * style.size / 100)
    align = {"bottom": 2, "middle": 5, "top": 8}[style.position]
    margin_v = round(height * style.margin / 100)
    border_style = 4 if style.box else 1  # 4 = caixa (BackColour) + contorno (extensao do libass)
    back = ass_color(style.box_color, style.box_opacity) if style.box else ass_color("#000000", 0.6)
    fields = [
        "Default", style.font, str(font_px), ass_color(style.color), ass_color(style.highlight_color),
        ass_color(style.outline_color), back, "-1" if style.bold else "0", "-1" if style.italic else "0",
        "0", "0", "100", "100", "0", "0", str(border_style), f"{style.outline * k:.2f}",
        f"{style.shadow * k:.2f}", str(align), str(round(width * 0.05)), str(round(width * 0.05)),
        str(margin_v), "1",
    ]
    return (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {width}\nPlayResY: {height}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: {','.join(fields)}\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def _entrance(style: SubtitleStyle) -> str:
    tags = ""
    if style.glow:
        tags += f"\\blur{style.glow:g}"
    if style.animation == "fade":
        tags += "\\fad(120,100)"
    elif style.animation == "pop":
        tags += "\\fscx80\\fscy80\\t(0,110,\\fscx100\\fscy100)"
    return "{" + tags + "}" if tags else ""


def _word_times(seg: Segment, n: int) -> list[float]:
    """Inicio de cada palavra exibida. Se o texto foi editado e o numero de palavras mudou,
    distribui o tempo da legenda proporcionalmente ao tamanho das palavras."""
    if seg.words and len(seg.words) == n:
        return [max(seg.start, min(w.start, seg.end)) for w in seg.words]
    tokens = seg.text.split()
    weights = [max(1, len(t)) for t in tokens] or [1]
    total, acc, out = sum(weights), 0.0, []
    for wgt in weights:
        out.append(seg.start + (seg.end - seg.start) * acc / total)
        acc += wgt
    return out


def _caption_text(seg: Segment, style: SubtitleStyle) -> str:
    text = seg.text.upper() if style.uppercase else seg.text
    return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())


def events(segments: Iterable[Segment], style: SubtitleStyle) -> list[str]:
    out: list[str] = []
    hl = ass_color(style.highlight_color) + "&"   # tags de override terminam com "&"
    base = ass_color(style.color) + "&"
    for seg in segments:
        text = _caption_text(seg, style)
        if not text:
            continue
        if style.highlight == "none":
            body = _escape(text).replace("\n", "\\N")
            out.append(f"Dialogue: 0,{_ass_time(seg.start)},{_ass_time(seg.end)},Default,,0,0,0,,"
                       f"{_entrance(style)}{body}")
            continue
        # karaoke: um evento por palavra, com a palavra atual destacada
        lines = [line.split() for line in text.split("\n")]
        flat = [w for line in lines for w in line]
        starts = _word_times(seg, len(flat))
        for i in range(len(flat)):
            t0 = seg.start if i == 0 else starts[i]
            t1 = starts[i + 1] if i + 1 < len(flat) else seg.end
            if t1 - t0 < 0.01:
                continue
            parts, k = [], 0
            for li, line in enumerate(lines):
                words = []
                for w in line:
                    w_esc = _escape(w)
                    if k == i:
                        if style.highlight == "pop":
                            w_esc = (f"{{\\c{hl}\\fscx118\\fscy118\\t(0,90,\\fscx100\\fscy100)}}"
                                     f"{w_esc}{{\\c{base}\\fscx100\\fscy100}}")
                        elif style.highlight == "color":
                            w_esc = f"{{\\c{hl}}}{w_esc}{{\\c{base}}}"
                    elif k > i and style.highlight == "reveal":
                        w_esc = f"{{\\alpha&HFF&}}{w_esc}{{\\alpha&H00&}}"
                    words.append(w_esc)
                    k += 1
                parts.append(" ".join(words))
                if li < len(lines) - 1:
                    parts.append("\\N")
            glow = f"{{\\blur{style.glow:g}}}" if style.glow else ""
            entrance = _entrance(style) if i == 0 else glow
            body = "".join(parts)
            out.append(f"Dialogue: 0,{_ass_time(t0)},{_ass_time(t1)},Default,,0,0,0,,{entrance}{body}")
    return out


def write_styled_ass(segments: Iterable[Segment], path: Path, style: SubtitleStyle,
                     width: int, height: int) -> Path:
    path.write_text(header(style, width, height) + "\n".join(events(segments, style)) + "\n", encoding="utf-8")
    return path


def sample_segments(duration: float = 3.0) -> list[Segment]:
    """Legenda de exemplo para a previa da tela de estilos."""
    text = "Hoje vamos aprender\nfunções do primeiro grau"
    words, t = [], 0.2
    for w in text.split():
        words.append(Word(start=t, end=t + 0.3, text=w))
        t += 0.35
    return [Segment(start=0.0, end=duration, text=text, words=words)]
