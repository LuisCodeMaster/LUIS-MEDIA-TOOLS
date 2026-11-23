"""Limpeza da fala: acha pausas longas e vicios de linguagem ("é…", "ãh", "hum", "né") a partir
das palavras com tempo do Whisper, e aplica os cortes aprovados no video e nas legendas.

Os cortes ficam no `<nome>.captions.json` (lista `cuts`), entao o usuario revisa, liga e
desliga cada um no app (lista + linha do tempo) antes de o video final ser gerado.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .models import Segment, Span, Word
from .segmentation import normalize, wrap_two_lines

CutKind = Literal["pausa", "vicio", "inicio", "fim", "manual"]

# Hesitacoes puras: cortadas por padrao
# (nada de "um": em portugues e numero/artigo)
STRONG_FILLERS = {"aa", "aah", "ahn", "ann", "eh", "ehh", "ee", "eee", "eeh", "hum", "humm", "hm",
                  "hmm", "hmmm", "uhm", "uh", "umm", "er", "erm"}
# Palavras que as vezes sao vicio e as vezes nao: sugeridas, mas desmarcadas
SOFT_FILLERS = {"ne", "tipo", "entao", "assim", "beleza", "ok", "certo", "ai", "ah"}
LABELS = {"pausa": "Pausa", "vicio": "Vício", "inicio": "Silêncio no começo", "fim": "Silêncio no fim",
          "manual": "Corte manual"}

# Prompt que faz o Whisper escrever as hesitacoes em vez de omiti-las
FILLER_PROMPT = "Hum, é... ãh, então, tipo, né? Ahn, é."


class Cut(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    kind: CutKind = "pausa"
    label: str = ""
    enabled: bool = True

    @model_validator(mode="after")
    def _order(self) -> Cut:
        if self.end <= self.start:
            raise ValueError("corte precisa terminar depois de comecar")
        return self

    @property
    def duration(self) -> float:
        return self.end - self.start


class CleanupSettings(BaseModel):
    """Parametros de deteccao (espelha o CleanupConfig das configuracoes)."""

    pauses: bool = True
    min_pause_s: float = 0.8      # pausas a partir daqui sao encurtadas
    keep_pause_s: float = 0.3     # quanto de respiro fica no lugar da pausa
    max_pause_s: float = 6.0      # pausas maiores sao mantidas (demonstracao, escrita no quadro)
    fillers: bool = True
    trim_ends: bool = True


def _bare(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z]", "", t)


def _squeeze(t: str) -> str:
    """'ééééé' -> 'ee', 'hummmm' -> 'humm' (o Whisper alonga as hesitacoes de varios jeitos)."""
    return re.sub(r"(.)\1{2,}", r"\1\1", t)


def filler_kind(words: Sequence[Word], i: int) -> Literal["strong", "soft"] | None:
    w = words[i]
    raw = w.text.strip()
    bare = _squeeze(_bare(raw))
    if not bare:
        return None
    gap_before = w.start - words[i - 1].end if i > 0 else 1.0
    gap_after = words[i + 1].start - w.end if i + 1 < len(words) else 1.0
    dur = w.end - w.start
    alone = gap_before >= 0.2 and gap_after >= 0.2
    if bare in STRONG_FILLERS:
        return "strong"
    if bare in ("e", "a"):  # "é..." / "e..." de hesitacao: alongado ou isolado entre pausas
        if "..." in raw or "…" in raw or dur >= 0.5 or (alone and dur >= 0.25):
            return "strong"
        return None
    if bare in SOFT_FILLERS:
        trailing = raw[-1:] in {",", "?", "…", "."} or gap_after >= 0.25
        if bare == "ne" and trailing:
            return "soft"
        if bare != "ne" and raw.endswith(",") and (i == 0 or gap_before >= 0.15 or bare in ("tipo", "assim")):
            return "soft"
    return None


def _quiet(env: Sequence[float] | None, rate: float, a: float, b: float, speech_level: float) -> bool:
    """O trecho [a, b] esta realmente em silencio? (evita cortar som de demonstracao)."""
    if not env or b - a < 0.05:
        return True
    lo, hi = max(0, int(a * rate)), min(len(env), int(b * rate) + 1)
    chunk = sorted(env[lo:hi])
    if not chunk:
        return True
    p90 = chunk[min(len(chunk) - 1, int(len(chunk) * 0.9))]
    return p90 <= max(0.02, 0.35 * speech_level)


def speech_level(env: Sequence[float] | None, rate: float, words: Sequence[Word]) -> float:
    if not env:
        return 1.0
    vals = sorted(env[int(w.start * rate)] for w in words[:: max(1, len(words) // 400)]
                  if int(w.start * rate) < len(env))
    return vals[len(vals) // 2] if vals else 1.0


def all_words(captions: Sequence[Segment]) -> list[Word]:
    words = [w for c in captions for w in c.words if w.text.strip()]
    return sorted(words, key=lambda w: w.start)


def detect_cuts(captions: Sequence[Segment], duration: float, cfg: CleanupSettings | None = None,
                envelope: Sequence[float] | None = None, rate: float = 50.0) -> list[Cut]:
    """Sugestoes de corte. Pausas e hesitacoes puras vem marcadas; vicios ambiguos (né, tipo)
    e pausas com som de fundo vem desmarcados para o usuario decidir."""
    cfg = cfg or CleanupSettings()
    words = all_words(captions)
    if not words:
        return []
    level = speech_level(envelope, rate, words)
    cuts: list[Cut] = []
    half = cfg.keep_pause_s / 2
    if cfg.pauses:
        if cfg.trim_ends and words[0].start > cfg.min_pause_s:
            end = words[0].start - 0.25
            if end > 0.1:
                cuts.append(Cut(start=0, end=end, kind="inicio", label=LABELS["inicio"]))
        for a, b in zip(words, words[1:], strict=False):
            gap = b.start - a.end
            if cfg.min_pause_s <= gap <= cfg.max_pause_s:
                s, e = a.end + half, b.start - half
                quiet = _quiet(envelope, rate, s, e, level)
                cuts.append(Cut(start=s, end=e, kind="pausa", enabled=quiet,
                                label=f"Pausa de {gap:.1f} s" + ("" if quiet else " (com som)")))
        if cfg.trim_ends and duration - words[-1].end > cfg.min_pause_s:
            s = words[-1].end + 0.4
            if duration - s > 0.1:
                cuts.append(Cut(start=s, end=duration, kind="fim", label=LABELS["fim"]))
    if cfg.fillers:
        for i, w in enumerate(words):
            kind = filler_kind(words, i)
            if kind is None:
                continue
            # o corte do vicio engole o silencio em volta dele (deixando o respiro normal),
            # senao sobrariam pedacinhos de silencio entre a pausa e o "é..."
            lo = words[i - 1].end if i > 0 else 0.0
            hi = words[i + 1].start if i + 1 < len(words) else duration
            s, e = max(lo, w.start - 0.04), min(hi, w.end + 0.04)
            if 0 < w.start - lo <= cfg.max_pause_s and w.start - lo > cfg.keep_pause_s:
                s = min(s, lo + half)
            if 0 < hi - w.end <= cfg.max_pause_s and hi - w.end > cfg.keep_pause_s:
                e = max(e, hi - half)
            if e - s >= 0.05:
                cuts.append(Cut(start=s, end=e, kind="vicio", enabled=kind == "strong",
                                label=f"“{w.text.strip(' ,.?!…')}”" + ("" if kind == "strong" else " (talvez)")))
    return sorted(cuts, key=lambda c: (c.start, c.end))


# ------------------------------------------------------------------ aplicar
def active_spans(cuts: Sequence[Cut]) -> list[Span]:
    """Uniao dos cortes ligados (ordenada, sem sobreposicao)."""
    out: list[Span] = []
    for c in sorted((c for c in cuts if c.enabled), key=lambda c: c.start):
        if out and c.start <= out[-1].end + 0.02:
            out[-1] = Span(start=out[-1].start, end=max(out[-1].end, c.end))
        else:
            out.append(Span(start=c.start, end=c.end))
    return out


def kept_spans(cuts: Sequence[Cut], duration: float, min_len: float = 0.08) -> list[Span]:
    keep, cursor = [], 0.0
    for s in active_spans(cuts):
        if s.start - cursor >= min_len:
            keep.append(Span(start=cursor, end=min(s.start, duration)))
        cursor = max(cursor, s.end)
    if duration - cursor >= min_len:
        keep.append(Span(start=cursor, end=duration))
    return keep


def removed_seconds(cuts: Sequence[Cut], duration: float | None = None) -> float:
    spans = active_spans(cuts)
    if duration is not None:
        spans = [Span(start=min(s.start, duration), end=min(s.end, duration)) for s in spans
                 if s.start < duration]
    return sum(s.end - s.start for s in spans)


class TimeMap:
    """Tempo do video original -> tempo do video editado."""

    def __init__(self, cuts: Sequence[Cut]) -> None:
        self.spans = active_spans(cuts)

    def __call__(self, t: float) -> float:
        removed = 0.0
        for s in self.spans:
            if s.start >= t:
                break
            removed += min(t, s.end) - s.start
        return max(0.0, t - removed)

    def inside(self, t: float) -> bool:
        return any(s.start <= t < s.end for s in self.spans)


def remap_captions(captions: Sequence[Segment], cuts: Sequence[Cut], max_chars: int = 42) -> list[Segment]:
    """Legendas no tempo do video editado, sem as palavras que cairam dentro dos cortes."""
    tm = TimeMap(cuts)
    if not tm.spans:
        return [c.model_copy(deep=True) for c in captions]
    out: list[Segment] = []
    for c in captions:
        words = c.words
        kept = [w for w in words if not tm.inside((w.start + w.end) / 2)]
        if words and not kept:
            continue  # legenda inteira era vicio/pausa
        new_words = [w.model_copy(update={"start": tm(w.start), "end": max(tm(w.end), tm(w.start) + 0.01)})
                     for w in kept]
        if len(kept) == len(words):
            text = c.text
            start, end = tm(c.start), tm(c.end)
        else:
            text = " ".join(w.text.strip() for w in kept)
            text = re.sub(r"\s+([,.!?;:…])", r"\1", text).strip(" ,;")
            if text and c.text[:1].isupper():
                text = text[0].upper() + text[1:]
            text = wrap_two_lines(normalize(text), max_chars)
            start = new_words[0].start if words[0] not in kept else tm(c.start)
            end = tm(c.end) if words[-1] in kept else new_words[-1].end + 0.15
        if not text.strip():
            continue
        end = max(end, start + 0.3)
        out.append(Segment(start=start, end=end, text=text, words=new_words))
    for a, b in zip(out, out[1:], strict=False):  # nunca sobrepor depois de encolher o tempo
        if a.end > b.start:
            a.end = max(a.start + 0.1, b.start)
    return out


def merge_detected(old: Sequence[Cut], new: Sequence[Cut]) -> list[Cut]:
    """Nova deteccao: troca as sugestoes automaticas e mantem os cortes manuais do usuario."""
    return sorted([*[c for c in old if c.kind == "manual"], *new], key=lambda c: (c.start, c.end))


def envelope_from_pcm(samples, sample_rate: int, rate: float = 50.0) -> list[float]:
    """Volume (RMS 0..1) a cada 1/rate s: usado na onda da linha do tempo e na checagem de silencio."""
    import numpy as np

    hop = max(1, int(sample_rate / rate))
    n = len(samples) // hop
    if n == 0:
        return []
    x = np.asarray(samples[: n * hop], dtype=np.float32).reshape(n, hop)
    if x.size and np.abs(x).max() > 1.5:  # int16
        x = x / 32768.0
    rms = np.sqrt((x * x).mean(axis=1))
    return [round(float(v), 4) for v in np.clip(rms * 3.0, 0, 1)]


def read_envelope_wav(path, rate: float = 50.0) -> list[float]:
    """Le um WAV PCM 16 bits em blocos (aulas longas nao estouram a memoria)."""
    import wave

    import numpy as np

    out: list[float] = []
    with wave.open(str(path), "rb") as w:
        sr, ch = w.getframerate(), w.getnchannels()
        hop = max(1, int(sr / rate))
        block = hop * int(rate) * 30  # 30 s por vez
        while True:
            raw = w.readframes(block)
            if not raw:
                break
            x = np.frombuffer(raw, dtype=np.int16)
            if ch > 1:
                x = x.reshape(-1, ch).mean(axis=1)
            out += envelope_from_pcm(x, sr, rate)
    return out
