"""Sincronia e ritmo das legendas.

- ``snap_to_speech``: o Whisper costuma marcar o inicio da primeira palavra de uma frase
  alguns decimos ANTES da voz (ele "puxa" o silencio anterior para a palavra). Resultado: a
  legenda aparece adiantada. Aqui o inicio de cada legenda (e de cada palavra, usado no
  destaque da palavra falada) e encaixado onde o volume do audio realmente sobe.
- ``PACES``: ritmo da legenda. Rapido = blocos curtos que trocam junto com a fala (estilo
  CapCut); Padrao = o recomendado para aulas (17 car./s); Devagar = mais tempo para ler.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Literal

from .models import Segment, Word
from .segmentation import SegmentationRules, segment_words

Pace = Literal["rapido", "padrao", "devagar"]
PACE_LABELS: dict[str, str] = {
    "rapido": "Rápido (troca junto com a fala)",
    "padrao": "Padrão (recomendado)",
    "devagar": "Devagar (mais tempo para ler)",
}
PACES: dict[str, dict] = {
    "rapido": {"max_duration": 2.6, "max_block_chars": 40, "split_chars": 30, "natural_pause": 0.3,
               "strong_pause": 0.5, "max_cps": 24.0, "min_duration": 0.5, "min_words_split": 2},
    "padrao": {},
    "devagar": {"max_duration": 6.5, "max_block_chars": 84, "split_chars": 64, "natural_pause": 0.6,
                "strong_pause": 0.9, "max_cps": 13.0, "min_duration": 1.2},
}
LEAD_S = 0.06       # a legenda entra um tiquinho antes da voz (padrao de legendagem)
MAX_SHIFT_S = 1.2   # nunca empurra mais que isso


def rules_for_pace(base: SegmentationRules, pace: str) -> SegmentationRules:
    return replace(base, **PACES.get(pace, {}))


def _level(env: Sequence[float], rate: float, words: Sequence[Word]) -> float:
    vals = sorted(env[min(len(env) - 1, int(((w.start + w.end) / 2) * rate))]
                  for w in words[:: max(1, len(words) // 400)])
    return vals[len(vals) // 2] if vals else 0.0


def speech_onset(env: Sequence[float], rate: float, lo: float, hi: float, thr: float) -> float | None:
    i0, i1 = max(0, int(lo * rate)), min(len(env), int(hi * rate) + 1)
    for i in range(i0, i1):
        if env[i] >= thr:
            return i / rate
    return None


def snap_to_speech(caps: Sequence[Segment], env: Sequence[float] | None, rate: float = 50.0) -> list[Segment]:
    """Encaixa o inicio de cada legenda (e das palavras) no inicio real da voz.

    So move para FRENTE e so quando o audio no inicio marcado esta em silencio, entao uma
    transcricao ja certa nao muda.
    """
    if not env or not caps:
        return list(caps)
    words = [w for c in caps for w in c.words]
    if not words:
        return list(caps)
    level = _level(env, rate, words)
    if level <= 0:
        return list(caps)
    thr = max(0.015, 0.3 * level)
    out: list[Segment] = []
    for c in caps:
        if not c.words:
            out.append(c)
            continue
        new_words: list[Word] = []
        prev_end = out[-1].words[-1].end if out and out[-1].words else 0.0
        for k, w in enumerate(c.words):
            gap_before = w.start - (new_words[-1].end if new_words else prev_end)
            start = w.start
            # so palavras depois de uma pausa (inicio de frase) costumam vir adiantadas
            if (k == 0 or gap_before > 0.12) and w.end - w.start > 0.12:
                cur = env[min(len(env) - 1, int(w.start * rate))]
                if cur < thr:
                    onset = speech_onset(env, rate, w.start, min(w.end - 0.05, w.start + MAX_SHIFT_S), thr)
                    if onset is not None and onset - LEAD_S > w.start:
                        start = onset - LEAD_S
            new_words.append(w.model_copy(update={"start": start}))
        shift = new_words[0].start - c.words[0].start
        start = c.start + shift if shift > 0 else c.start
        end = max(c.end, start + 0.4)
        out.append(c.model_copy(update={"start": start, "end": end, "words": new_words}))
    for a, b in zip(out, out[1:], strict=False):  # o fim estendido nao pode invadir a proxima
        if a.end > b.start - 0.04:
            a.end = max(a.start + 0.2, b.start - 0.04)
    return out


def resegment(caps: Sequence[Segment], rules: SegmentationRules, env: Sequence[float] | None = None,
              rate: float = 50.0) -> list[Segment]:
    """Refaz os blocos de legenda (novo ritmo) a partir das palavras, mantendo as correcoes de
    texto que o usuario ja fez (elas ficam nas palavras)."""
    from .captions import realign_words

    words = [w for c in caps for w in (c.words or realign_words(c, c.text.replace("\n", " ")).words)]
    if not words:
        return list(caps)
    return snap_to_speech(segment_words(words, rules), env, rate)


def shift_all(caps: Sequence[Segment], delta: float) -> list[Segment]:
    """Atrasa (+) ou adianta (-) todas as legendas."""
    def mv(t: float) -> float:
        return max(0.0, t + delta)

    return [c.model_copy(update={"start": mv(c.start), "end": max(mv(c.end), mv(c.start) + 0.05),
                                 "words": [w.model_copy(update={"start": mv(w.start), "end": mv(w.end)})
                                           for w in c.words]}) for c in caps]
