"""Estilos de legenda (estilo CapCut) e geracao do arquivo ASS.

Um estilo descreve fonte, cores (inclusive gradiente e duas cores alternadas), contorno,
caixa de fundo, posicao (ou um ponto livre arrastado na previa), animacao de entrada
(fade, pop, quicar, deslizar, maquina de escrever), destaque da palavra falada (cor, pop,
caixa colorida estilo marca-texto, karaoke), palavras-chave em destaque e emojis.

O mesmo ASS e usado na legenda queimada, nos cortes 9:16 e na previa da tela de estilos:
o que se ve na previa e exatamente o que sai no video. Emojis coloridos nao existem no
libass, entao sao imagens (Twemoji) sobrepostas pelo FFmpeg (veja ``emoji_plan``).

Tamanhos sao relativos ao lado menor do video (5 = 5%), entao o estilo funciona igual em
1080p, 4K ou 9:16.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import Segment, Word

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
Position = Literal["bottom", "middle", "top", "custom"]
Animation = Literal["none", "fade", "pop", "bounce", "slide", "typewriter"]
Highlight = Literal["none", "color", "pop", "box", "reveal"]

BUNDLED_FONTS = ["Poppins", "Poppins ExtraBold", "Poppins Black", "Anton", "Bebas Neue", "Archivo Black"]
SYSTEM_FONTS = ["Arial", "Segoe UI", "Verdana", "Impact", "Calibri", "Georgia"]
GRADIENT_BANDS = 6


def fonts_dir() -> Path:
    return Path(str(resources.files("luismedia") / "assets" / "fonts"))


def emoji_dir() -> Path:
    return Path(str(resources.files("luismedia") / "assets" / "emoji"))


class SubtitleStyle(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    font: str = "Arial"
    size: float = Field(5.0, ge=2, le=15)            # % do lado menor do video
    bold: bool = False
    italic: bool = False
    uppercase: bool = False
    color: str = "#FFFFFF"
    alt_colors: bool = False                         # duas cores alternadas (por linha/legenda)
    color2: str = "#FFE600"
    gradient: bool = False                           # gradiente vertical: color -> gradient_color
    gradient_color: str = "#FF7A00"
    outline_color: str = "#000000"
    outline: float = Field(1.5, ge=0, le=12)        # px na referencia 1080
    shadow: float = Field(1.0, ge=0, le=10)
    glow: float = Field(0.0, ge=0, le=10)            # desfoque do contorno (efeito neon)
    box: bool = False
    box_color: str = "#000000"
    box_opacity: float = Field(0.6, ge=0, le=1)
    position: Position = "bottom"
    margin: float = Field(3.2, ge=0, le=45)          # % da altura, a partir da borda
    pos_x: float = Field(50.0, ge=0, le=100)         # posicao livre (position="custom"), em %
    pos_y: float = Field(75.0, ge=0, le=100)
    animation: Animation = "fade"
    highlight: Highlight = "none"
    highlight_color: str = "#FFE600"
    max_words: int = Field(0, ge=0, le=12)           # 0 = automatico (pelo tamanho da linha)
    keywords: bool = False                           # destacar palavras-chave (IA + vocabulario)
    keyword_color: str = "#22D3EE"
    keyword_scale: float = Field(115, ge=100, le=160)  # % do tamanho
    emojis: bool = False                             # emojis automaticos acima da legenda
    emoji_size: float = Field(9.0, ge=4, le=20)      # % do lado menor

    @field_validator("color", "color2", "gradient_color", "outline_color", "box_color",
                     "highlight_color", "keyword_color")
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
    "Máquina de escrever": SubtitleStyle(font="Poppins", bold=True, size=4.6, outline=2.0, shadow=0.5,
                                         animation="typewriter", keywords=True, keyword_color="#FDE047",
                                         keyword_scale=100),
}

PRESETS_V: dict[str, SubtitleStyle] = {
    "CapCut amarelo": SubtitleStyle(font="Poppins Black", size=8.5, uppercase=True, outline=4.0, shadow=1.5,
                                    position="bottom", margin=28, animation="pop", highlight="pop",
                                    highlight_color="#FFE600", max_words=3),
    "Marca-texto": SubtitleStyle(font="Poppins Black", size=8.5, uppercase=True, outline=3.0, shadow=0,
                                 position="bottom", margin=26, animation="bounce", highlight="box",
                                 highlight_color="#7C3AED", max_words=3, emojis=True),
    "Gradiente fogo": SubtitleStyle(font="Anton", size=10.5, uppercase=True, color="#FFE600",
                                    gradient=True, gradient_color="#FF3D00", outline=4.5, shadow=1,
                                    position="middle", animation="slide", keywords=True,
                                    keyword_color="#FFFFFF", keyword_scale=125, max_words=3, emojis=True),
    "Duas cores": SubtitleStyle(font="Archivo Black", size=8.0, uppercase=True, alt_colors=True,
                                color2="#4ADE80", outline=3.5, shadow=1, position="bottom", margin=24,
                                animation="bounce", max_words=2),
    "Destaque verde": SubtitleStyle(font="Anton", size=10.0, uppercase=True, outline=4.5, shadow=0,
                                    position="middle", animation="pop", highlight="color",
                                    highlight_color="#39FF14", max_words=2),
    "Karaokê": SubtitleStyle(font="Bebas Neue", size=10.5, uppercase=True, outline=3.0, shadow=2,
                             position="bottom", margin=24, animation="none", highlight="reveal", max_words=4),
    "Máquina de escrever": SubtitleStyle(font="Poppins ExtraBold", size=7.5, outline=3.0, shadow=0,
                                         box=True, box_color="#111827", box_opacity=0.85,
                                         position="bottom", margin=24, animation="typewriter", max_words=5),
    "Caixa minimal": SubtitleStyle(font="Poppins", bold=True, size=6.5, outline=0, shadow=0, box=True,
                                   box_opacity=0.75, position="bottom", margin=22, animation="fade", max_words=5),
    "Neon": SubtitleStyle(font="Archivo Black", size=8.0, uppercase=True, color="#FFFFFF",
                          outline_color="#E11DFF", outline=3.5, glow=4, shadow=0, position="middle",
                          animation="pop", highlight="color", highlight_color="#22D3EE", max_words=3),
}


# ---------------------------------------------------------------------- utilidades
def ass_color(hex_rgb: str, opacity: float = 1.0) -> str:
    """#RRGGBB -> &HAABBGGRR (no ASS o alfa e invertido: 00 = opaco)."""
    r, g, b = hex_rgb[1:3], hex_rgb[3:5], hex_rgb[5:7]
    alpha = round((1 - opacity) * 255)
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _tag_color(hex_rgb: str) -> str:
    return ass_color(hex_rgb) + "&"  # dentro de {\c...} a cor termina com "&"


def _mix(a: str, b: str, t: float) -> str:
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ca, cb, strict=True))


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def _ass_time(seconds: float) -> str:
    total_cs = max(0, round(seconds * 100))
    h, rem = divmod(total_cs, 360_000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def norm_word(text: str) -> str:
    """Minusculas, sem acento e sem pontuacao: "Funções!" -> "funcoes"."""
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w]", "", t)


def keyword_set(keywords: Iterable[str] | None) -> set[str]:
    out: set[str] = set()
    for k in keywords or []:
        tokens = [norm_word(t) for t in k.split()]
        if len(tokens) == 1 and tokens[0]:
            out.add(tokens[0])
        else:  # termo composto: destaca as palavras "fortes" dele
            out.update(t for t in tokens if len(t) >= 4)
    return out


# ---------------------------------------------------------------------- layout
@dataclass(frozen=True)
class Layout:
    an: int          # alinhamento ASS (2 = base centralizada, 5 = centro, 8 = topo)
    x: int
    y: int
    font_px: int
    line_h: float

    def text_box(self, n_lines: int) -> tuple[float, float]:
        """(topo, base) aproximados do bloco de texto, para gradiente e emojis."""
        h = n_lines * self.line_h
        if self.an == 2:
            return self.y - h, self.y
        if self.an == 8:
            return self.y, self.y + h
        return self.y - h / 2, self.y + h / 2


def layout(style: SubtitleStyle, width: int, height: int) -> Layout:
    font_px = round(min(width, height) * style.size / 100)
    margin_v = height * style.margin / 100
    if style.position == "custom":
        an, x, y = 5, width * style.pos_x / 100, height * style.pos_y / 100
    elif style.position == "top":
        an, x, y = 8, width / 2, margin_v
    elif style.position == "middle":
        an, x, y = 5, width / 2, height / 2
    else:
        an, x, y = 2, width / 2, height - margin_v
    return Layout(an=an, x=round(x), y=round(y), font_px=font_px, line_h=font_px * 1.22)


def header(style: SubtitleStyle, width: int, height: int) -> str:
    base = min(width, height)
    k = base / 1080  # contorno/sombra definidos na referencia 1080
    lay = layout(style, width, height)
    margin_v = round(height * style.margin / 100)
    border_style = 4 if style.box else 1  # 4 = caixa (BackColour) + contorno (extensao do libass)
    back = ass_color(style.box_color, style.box_opacity) if style.box else ass_color("#000000", 0.6)
    margin_h = str(round(width * 0.05))
    fields = [
        "Default", style.font, str(lay.font_px), ass_color(style.color), ass_color(style.highlight_color),
        ass_color(style.outline_color), back, "-1" if style.bold else "0", "-1" if style.italic else "0",
        "0", "0", "100", "100", "0", "0", str(border_style), f"{style.outline * k:.2f}",
        f"{style.shadow * k:.2f}", str(lay.an), margin_h, margin_h, str(margin_v), "1",
    ]
    styles = f"Style: {','.join(fields)}\n"
    if style.highlight == "box":
        # Camada so com a caixa colorida (BorderStyle 3): o contorno opaco vira o fundo da palavra
        pad = max(4.0, lay.font_px * 0.13)
        box = [*fields]
        box[0], box[3], box[5], box[6] = "Box", "&HFF000000", ass_color(style.highlight_color), "&HFF000000"
        box[15], box[16], box[17] = "3", f"{pad:.2f}", "0"
        styles += f"Style: {','.join(box)}\n"
    return (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {width}\nPlayResY: {height}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"{styles}\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


# ---------------------------------------------------------------------- eventos
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


def _position_tag(style: SubtitleStyle, lay: Layout, entrance: bool, dy: int = 0) -> str:
    y = lay.y + dy
    if entrance and style.animation == "slide":
        d = round(lay.font_px * 0.9)
        return f"\\an{lay.an}\\move({lay.x},{y + d},{lay.x},{y},0,170)"
    return f"\\an{lay.an}\\pos({lay.x},{y})"


def _anim_tag(style: SubtitleStyle, entrance: bool) -> str:
    if not entrance:
        return ""
    return {
        "fade": "\\fad(120,100)",
        "pop": "\\fscx80\\fscy80\\t(0,110,\\fscx100\\fscy100)",
        "bounce": ("\\fscx65\\fscy65\\t(0,100,\\fscx114\\fscy114)\\t(100,180,\\fscx95\\fscy95)"
                   "\\t(180,240,\\fscx100\\fscy100)"),
        "slide": "\\fad(90,0)",
    }.get(style.animation, "")


class _Body:
    """Monta o texto de um evento: palavra ativa, palavras-chave, revelacao e cores."""

    def __init__(self, style: SubtitleStyle, lines: list[list[str]], keywords: set[str], lay: Layout,
                 caption_index: int) -> None:
        self.s, self.lines, self.kw, self.lay, self.ci = style, lines, keywords, lay, caption_index

    def line_color(self, li: int) -> str:
        s = self.s
        if not s.alt_colors:
            return s.color
        if len(self.lines) > 1:
            return s.color if li % 2 == 0 else s.color2
        return s.color if self.ci % 2 == 0 else s.color2

    def build(self, active: int | None, visible_chars: int | None = None, *, box_layer: bool = False,
              base_override: str | None = None) -> str:
        s, out, k, shown = self.s, [], 0, 0
        kw_fs = round(self.lay.font_px * s.keyword_scale / 100)
        for li, line in enumerate(self.lines):
            base = base_override or self.line_color(li)
            words = []
            for w in line:
                piece = _escape(w)
                if visible_chars is not None:  # maquina de escrever: corta no meio da palavra
                    n = len(w)
                    if shown >= visible_chars:
                        piece = f"{{\\alpha&HFF&}}{piece}{{\\alpha&H00&}}"
                    elif shown + n > visible_chars:
                        cut = visible_chars - shown
                        piece = f"{_escape(w[:cut])}{{\\alpha&HFF&}}{_escape(w[cut:])}{{\\alpha&H00&}}"
                    shown += n
                is_kw = s.keywords and norm_word(w) in self.kw
                pre, post = "", ""
                if is_kw and kw_fs != self.lay.font_px:
                    pre += f"\\fs{kw_fs}"
                    post += f"\\fs{self.lay.font_px}"
                if box_layer:
                    if k == active:
                        pre += "\\3a&H00&"
                        post += "\\3a&HFF&"
                elif k == active and s.highlight in ("color", "pop"):
                    pre += f"\\c{_tag_color(s.highlight_color)}"
                    post += f"\\c{_tag_color(base)}"
                    if s.highlight == "pop":
                        pre += "\\fscx118\\fscy118\\t(0,90,\\fscx100\\fscy100)"
                        post += "\\fscx100\\fscy100"
                elif is_kw:
                    pre += f"\\c{_tag_color(s.keyword_color)}"
                    post += f"\\c{_tag_color(base)}"
                if not box_layer and active is not None and k > active and s.highlight == "reveal":
                    pre += "\\alpha&HFF&"
                    post += "\\alpha&H00&"
                words.append(f"{{{pre}}}{piece}{{{post}}}" if pre else piece)
                k += 1
            line_txt = " ".join(words)
            if not box_layer and base != s.color:
                line_txt = f"{{\\c{_tag_color(base)}}}" + line_txt
            out.append(line_txt)
        return "\\N".join(out)


def events(segments: Iterable[Segment], style: SubtitleStyle, *, width: int = 1080, height: int = 1920,
           keywords: Iterable[str] | None = None) -> list[str]:
    lay = layout(style, width, height)
    kw = keyword_set(keywords) if style.keywords else set()
    glow = f"\\blur{style.glow:g}" if style.glow else ""
    out: list[str] = []
    for ci, seg in enumerate(segments):
        text = _caption_text(seg, style)
        if not text:
            continue
        lines = [line.split() for line in text.split("\n")]
        flat = [w for line in lines for w in line]
        body = _Body(style, lines, kw, lay, ci)

        # estados: (inicio, fim, palavra ativa)
        if style.highlight == "none":
            states: list[tuple[float, float, int | None]] = [(seg.start, seg.end, None)]
        else:
            starts = _word_times(seg, len(flat))
            states = []
            for i in range(len(flat)):
                t0 = seg.start if i == 0 else starts[i]
                t1 = starts[i + 1] if i + 1 < len(flat) else seg.end
                if t1 - t0 >= 0.01:
                    states.append((t0, t1, i))
        # (inicio, fim, palavra ativa, letras visiveis, e a entrada?)
        expanded: list[tuple[float, float, int | None, int | None, bool]] = []
        for si, (t0, t1, act) in enumerate(states):
            if si == 0 and style.animation == "typewriter":
                total = sum(len(w) for w in flat)
                dur = min(0.45, (t1 - t0) * 0.6, 0.03 * total)
                steps = max(1, min(total, 14))
                for j in range(steps):
                    a = t0 + dur * j / steps
                    b = t0 + dur * (j + 1) / steps if j + 1 < steps else t1
                    vis = None if j + 1 == steps else max(1, round(total * (j + 1) / steps))
                    if b - a >= 0.01:
                        expanded.append((a, b, act, vis, j == 0))
            else:
                expanded.append((t0, t1, act, None, si == 0))

        top, bottom = lay.text_box(len(lines))
        for t0, t1, act, vis, first in expanded:
            pos = _position_tag(style, lay, first)
            anim = _anim_tag(style, first)
            times = f"{_ass_time(t0)},{_ass_time(t1)}"
            if style.highlight == "box" and act is not None:
                # a caixa comeca invisivel (\3a&HFF&) e so a palavra ativa a mostra
                # a caixa do libass fica um pouco abaixo do texto (descendentes da fonte): sobe um pouco
                bpos = _position_tag(style, lay, first, dy=-round(lay.font_px * 0.08))
                out.append(f"Dialogue: 0,{times},Box,,0,0,0,,{{{bpos}{anim}\\3a&HFF&}}"
                           f"{body.build(act, vis, box_layer=True)}")
            if style.gradient:
                for b in range(GRADIENT_BANDS):
                    c = _mix(style.color, style.gradient_color, b / (GRADIENT_BANDS - 1))
                    y0 = 0 if b == 0 else round(top + (bottom - top) * b / GRADIENT_BANDS)
                    y1 = height if b == GRADIENT_BANDS - 1 else round(top + (bottom - top) * (b + 1) / GRADIENT_BANDS)
                    out.append(f"Dialogue: 1,{times},Default,,0,0,0,,{{{pos}{anim}{glow}"
                               f"\\clip(0,{y0},{width},{y1})}}{body.build(act, vis, base_override=c)}")
            else:
                out.append(f"Dialogue: 1,{times},Default,,0,0,0,,{{{pos}{anim}{glow}}}{body.build(act, vis)}")
    return out


def write_styled_ass(segments: Iterable[Segment], path: Path, style: SubtitleStyle,
                     width: int, height: int, keywords: Iterable[str] | None = None) -> Path:
    evs = events(segments, style, width=width, height=height, keywords=keywords)
    path.write_text(header(style, width, height) + "\n".join(evs) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------- emojis
EMOJI_WORDS = {
    "1f525": "fogo incrivel top demais sensacional brabo",
    "1f4a1": "ideia ideias dica dicas insight",
    "1f4b0": "dinheiro lucro renda grana reais investimento investir",
    "26a0": "importante atencao cuidado aviso",
    "2705": "certo correto sucesso aprovado pronto",
    "274c": "erro erros errado falha proibido",
    "2764": "amor coracao amo paixao",
    "23f0": "tempo hora horas minutos prazo",
    "1f4c8": "resultado resultados crescer crescimento aumentar aumento",
    "1f4c9": "queda cair diminuir prejuizo",
    "1f4da": "estudar estudo estudos aprender aprendizado aula aulas curso",
    "1f4d6": "livro livros leitura ler",
    "2753": "pergunta perguntas duvida duvidas porque",
    "1f3af": "objetivo objetivos meta metas foco alvo",
    "26a1": "rapido rapida energia velocidade",
    "1f92b": "segredo segredos",
    "1f3b5": "musica musicas cancao",
    "1f4bb": "computador programacao codigo programar software",
    "1f4f1": "celular telefone aplicativo app",
    "1f680": "foguete lancamento decolar",
    "1f30d": "mundo planeta global terra",
    "1f3e0": "casa lar",
    "1f4bc": "trabalho emprego empresa negocio negocios",
    "1f48a": "remedio saude",
    "1f354": "comida comer fome",
    "1f4a7": "agua",
    "2600": "sol verao calor",
    "1f634": "dormir sono cansado",
    "1f604": "feliz alegria alegre",
    "1f622": "triste tristeza",
    "1f602": "engracado rir risada",
    "1f914": "pensar pense pensamento imagine",
    "1f4aa": "forca forte treino",
    "1f389": "parabens comemorar festa",
    "2b50": "estrela estrelas destaque",
    "1f3c6": "campeao vencedor vitoria ganhar premio",
    "1f440": "olha veja olhem",
    "270d": "escrever anotar anote anotacoes",
    "1f9e0": "cerebro inteligencia mente memoria",
    "1f511": "chave solucao",
    "1f6a8": "alerta perigo urgente",
    "1f522": "numero numeros matematica calculo calcular",
    "1f52c": "ciencia quimica experimento laboratorio",
    "1f4ac": "mensagem conversa comentario comentarios",
    "1f3ac": "video videos filme",
    "1f3ae": "jogo jogos game games",
    "1f4dd": "exercicio exercicios prova resumo",
    "1f91d": "parceria juntos equipe acordo",
}
_WORD_TO_EMOJI = {w: code for code, words in EMOJI_WORDS.items() for w in words.split()}


def emoji_for(word: str) -> str | None:
    w = norm_word(word)
    return _WORD_TO_EMOJI.get(w) or (_WORD_TO_EMOJI.get(w[:-1]) if w.endswith("s") else None)


@dataclass(frozen=True)
class EmojiShow:
    code: str
    start: float
    end: float
    x: int       # canto superior esquerdo, em pixels do video
    y: int
    size: int

    @property
    def png(self) -> Path:
        return emoji_dir() / f"{self.code}.png"


def emoji_plan(segments: Iterable[Segment], style: SubtitleStyle, width: int, height: int,
               keywords: Iterable[str] | None = None, min_gap: float = 2.5) -> list[EmojiShow]:
    """No maximo um emoji por legenda, centralizado logo acima do texto, com folga de
    ``min_gap`` segundos entre emojis (para nao poluir). Palavras-chave tem preferencia."""
    if not style.emojis:
        return []
    lay = layout(style, width, height)
    kw = keyword_set(keywords)
    size = round(min(width, height) * style.emoji_size / 100)
    plans: list[EmojiShow] = []
    last_end = -1e9
    for seg in segments:
        words = seg.text.split()
        if not words or seg.start - last_end < min_gap:
            continue
        ranked = sorted(words, key=lambda w: norm_word(w) not in kw)  # palavras-chave primeiro
        code = next((c for c in (emoji_for(w) for w in ranked) if c), None)
        if not code or not (emoji_dir() / f"{code}.png").exists():
            continue
        top, _ = lay.text_box(len(seg.text.split("\n")))
        y = max(0, round(top - size - lay.font_px * 0.25))
        plans.append(EmojiShow(code, seg.start, seg.end, round(lay.x - size / 2), y, size))
        last_end = seg.end
    return plans


def emoji_overlay(plan: list[EmojiShow], in_label: str, out_label: str,
                  first_input: int) -> tuple[list[str], str]:
    """Entradas extras do FFmpeg + trecho do filtergraph que sobrepoe os emojis.

    Um input por emoji diferente (nao por ocorrencia): a mesma imagem aparece em varios
    momentos com ``enable=between(t,a,b)+...``, entao o custo nao cresce com a aula.
    """
    if not plan:
        return [], f"[{in_label}]null[{out_label}]"
    by_code: dict[str, list[EmojiShow]] = {}
    for p in plan:
        by_code.setdefault(p.code, []).append(p)
    inputs: list[str] = []
    parts: list[str] = []
    cur = in_label
    for n, shows in enumerate(by_code.values()):
        idx = first_input + n
        inputs += ["-loop", "1", "-i", str(shows[0].png)]
        nxt = out_label if n == len(by_code) - 1 else f"em{n}"
        # cada ocorrencia tem sua posicao (a legenda pode ter 1 ou 2 linhas)
        x_expr = "+".join(f"{s.x}*between(t\\,{s.start:.3f}\\,{s.end:.3f})" for s in shows)
        y_expr = "+".join(f"{s.y}*between(t\\,{s.start:.3f}\\,{s.end:.3f})" for s in shows)
        enable = "+".join(f"between(t\\,{s.start:.3f}\\,{s.end:.3f})" for s in shows)
        parts.append(f"[{idx}:v]scale={shows[0].size}:{shows[0].size},format=rgba[ei{n}];"
                     f"[{cur}][ei{n}]overlay=x={x_expr}:y={y_expr}:eval=frame:"
                     f"enable={enable}:shortest=1[{nxt}]")
        cur = nxt
    return inputs, ";".join(parts)


def sample_segments(duration: float = 3.0) -> list[Segment]:
    """Legenda de exemplo para a previa da tela de estilos."""
    text = "Hoje vamos aprender\nfunções do primeiro grau"
    words, t = [], 0.2
    for w in text.split():
        words.append(Word(start=t, end=t + 0.3, text=w))
        t += 0.35
    return [Segment(start=0.0, end=duration, text=text, words=words)]


SAMPLE_KEYWORDS = ["aprender", "funções"]
