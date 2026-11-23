"""Legenda editavel: o arquivo `<nome>.captions.json` e a fonte da verdade depois da transcricao.

Tudo que mostra texto (SRT/VTT/ASS, legenda queimada, cortes 9:16) e gerado a partir dele,
entao uma correcao feita no editor do app vale para todos os entregaveis.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel

from .cleanup import Cut
from .models import Segment, Word
from .segmentation import normalize, wrap_two_lines


class CaptionDoc(BaseModel):
    video: str
    width: int = 1920
    height: int = 1080
    approved: bool = False
    keywords: list[str] = []  # palavras-chave em destaque (sugeridas pela IA, editaveis)
    duration: float = 0.0     # duracao do video (para os cortes do fim)
    cuts: list[Cut] = []      # pausas e vicios sugeridos/aprovados (ver core.cleanup)
    pace: str = "padrao"      # ritmo usado para montar os blocos (core.sync)
    sync_offset: float = 0.0  # ajuste manual de sincronia ja aplicado (so informativo)
    av_offset: float | None = None  # atraso do audio no arquivo ja considerado (None = versao antiga)
    voice_sync: bool = False  # legendas ja encaixadas no inicio real da voz (detector de voz)
    captions: list[Segment]

    @classmethod
    def load(cls, path: Path) -> CaptionDoc:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, path: Path) -> Path:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(self.model_dump_json(indent=1), encoding="utf-8")
        tmp.replace(path)
        return path


def apply_replacements(text: str, replacements: dict[str, str]) -> str:
    """Troca palavras inteiras, sem diferenciar maiusculas: {"wisper": "Whisper"}."""
    for wrong, right in replacements.items():
        if wrong.strip():
            text = re.sub(rf"(?<!\w){re.escape(wrong.strip())}(?!\w)", right, text, flags=re.IGNORECASE)
    return text


def realign_words(seg: Segment, new_text: str) -> Segment:
    """Depois de editar o texto, refaz o tempo das palavras (usado no destaque karaoke).

    Mesmo numero de palavras: mantem os tempos originais. Senao, distribui a duracao da
    legenda proporcionalmente ao tamanho de cada palavra.
    """
    tokens = new_text.split()
    if seg.words and len(seg.words) == len(tokens):
        words = [w.model_copy(update={"text": t}) for w, t in zip(seg.words, tokens, strict=True)]
    else:
        total = sum(len(t) for t in tokens) or 1
        words, acc = [], 0
        for t in tokens:
            a = seg.start + (seg.end - seg.start) * acc / total
            acc += len(t)
            b = seg.start + (seg.end - seg.start) * acc / total
            words.append(Word(start=a, end=b, text=t))
    return Segment(start=seg.start, end=seg.end, text=new_text, words=words)


def apply_to_doc(doc: CaptionDoc, replacements: dict[str, str]) -> int:
    """Aplica as substituicoes em todas as legendas. Devolve quantas mudaram."""
    changed = 0
    for i, c in enumerate(doc.captions):
        new = apply_replacements(c.text, replacements)
        if new != c.text:
            doc.captions[i] = realign_words(c, new)
            changed += 1
    return changed


def rebalance(text: str, max_chars: int) -> str:
    return wrap_two_lines(normalize(text.replace("\n", " ")), max_chars)


def clip_window(captions: list[Segment], start: float, end: float) -> list[Segment]:
    """Legendas dentro de um corte, com o tempo relativo ao inicio do corte."""
    out = []
    for c in captions:
        if c.end <= start or c.start >= end:
            continue
        words = [w.model_copy(update={"start": max(0.0, w.start - start), "end": max(0.0, w.end - start)})
                 for w in c.words if start <= w.start < end]
        out.append(Segment(start=max(0.0, c.start - start), end=min(end - start, c.end - start),
                           text=c.text, words=words))
    return out


def to_json_preview(doc: CaptionDoc) -> str:  # util para depuracao
    return json.dumps([{"t": round(c.start, 2), "text": c.text} for c in doc.captions], ensure_ascii=False)
