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


# ------------------------------------------------------------------ detector de voz (Silero)
Region = tuple[float, float]


def speech_regions(audio, sample_rate: int = 16000) -> list[Region]:
    """Trechos com voz, pelo detector Silero que ja vem com o faster-whisper.

    Diferente do volume, ele reconhece a fala mesmo com musica ou ruido de fundo. Sem o
    faster-whisper instalado devolve [] (o encaixe cai para o metodo por volume)."""
    try:
        from faster_whisper.vad import VadOptions, get_speech_timestamps
    except Exception:  # noqa: BLE001
        return []
    opts = VadOptions(threshold=0.5, min_silence_duration_ms=100, speech_pad_ms=30, min_speech_duration_ms=60)
    ts = get_speech_timestamps(audio, opts, sampling_rate=sample_rate)
    return [(t["start"] / sample_rate, t["end"] / sample_rate) for t in ts]


def _inside(regions: Sequence[Region], t: float, tol: float = 0.03) -> bool:
    return any(a - tol <= t <= b + tol for a, b in regions)


def _next_start(regions: Sequence[Region], t: float, limit: float) -> float | None:
    return next((a for a, _ in regions if t < a <= limit), None)


def estimate_bias(caps: Sequence[Segment], regions: Sequence[Region]) -> float:
    """Quanto o Whisper esta adiantado (+) ou atrasado (-) em media nesta aula.

    Compara o inicio de cada frase que vem depois de uma pausa com o inicio real da voz. Com
    menos de 3 comparacoes confiaveis, nao arrisca (0)."""
    words = [w for c in caps for w in c.words]
    deltas = []
    for k, w in enumerate(words):
        gap = w.start - words[k - 1].end if k else 1.0
        if gap < 0.25:
            continue
        near = [a for a, _ in regions if w.start - 0.35 <= a <= w.start + MAX_SHIFT_S]
        if near:
            deltas.append(min(near, key=lambda a: abs(a - w.start)) - w.start)
    if len(deltas) < 3:
        return 0.0
    deltas.sort()
    bias = deltas[len(deltas) // 2]
    return 0.0 if abs(bias) < 0.05 else max(-0.3, min(0.6, bias))


def snap_to_regions(caps: Sequence[Segment], regions: Sequence[Region]) -> list[Segment]:
    """Encaixe pelo detector de voz: corrige o adiantamento medio de toda a aula e depois
    empurra cada inicio de frase que ainda caia antes da voz."""
    if not regions or not caps:
        return list(caps)
    bias = estimate_bias(caps, regions)
    out: list[Segment] = []
    for c in caps:
        words = [w.model_copy(update={"start": max(0.0, w.start + bias), "end": max(0.05, w.end + bias)})
                 for w in c.words]
        prev_end = out[-1].words[-1].end if out and out[-1].words else 0.0
        fixed: list[Word] = []
        for k, w in enumerate(words):
            gap = w.start - (fixed[-1].end if fixed else prev_end)
            start = w.start
            if (k == 0 or gap > 0.12) and not _inside(regions, w.start):
                nxt = _next_start(regions, w.start, min(w.end - 0.05, w.start + MAX_SHIFT_S))
                if nxt is not None:
                    start = nxt - LEAD_S
            fixed.append(w.model_copy(update={"start": max(start, w.start), "end": max(w.end, start + 0.05)}))
        start = max(0.0, c.start + bias)
        if fixed and fixed[0].start > words[0].start:  # inicio da frase empurrado ate a voz
            start = max(start, fixed[0].start)
        end = max(c.end + bias, start + 0.4)
        out.append(c.model_copy(update={"start": start, "end": end, "words": fixed}))
    for a, b in zip(out, out[1:], strict=False):
        if a.end > b.start - 0.04:
            a.end = max(a.start + 0.2, b.start - 0.04)
    return out


def snap(caps: Sequence[Segment], regions: Sequence[Region] | None, env: Sequence[float] | None,
         rate: float = 50.0) -> list[Segment]:
    """Melhor encaixe disponivel: detector de voz; sem ele, volume do audio."""
    if regions:
        return snap_to_regions(caps, regions)
    return snap_to_speech(caps, env, rate)


def resegment(caps: Sequence[Segment], rules: SegmentationRules, env: Sequence[float] | None = None,
              rate: float = 50.0, regions: Sequence[Region] | None = None) -> list[Segment]:
    """Refaz os blocos de legenda (novo ritmo) a partir das palavras, mantendo as correcoes de
    texto que o usuario ja fez (elas ficam nas palavras)."""
    from .captions import realign_words

    words = [w for c in caps for w in (c.words or realign_words(c, c.text.replace("\n", " ")).words)]
    if not words:
        return list(caps)
    new = segment_words(words, rules)
    # as palavras ja foram encaixadas antes: aqui so o encaixe por volume (nao reaplica o vies)
    return snap_to_speech(new, env, rate) if not regions else new


def shift_all(caps: Sequence[Segment], delta: float) -> list[Segment]:
    """Atrasa (+) ou adianta (-) todas as legendas."""
    def mv(t: float) -> float:
        return max(0.0, t + delta)

    return [c.model_copy(update={"start": mv(c.start), "end": max(mv(c.end), mv(c.start) + 0.05),
                                 "words": [w.model_copy(update={"start": mv(w.start), "end": mv(w.end)})
                                           for w in c.words]}) for c in caps]


def shift_cuts_for_bias(cuts, bias: float, duration: float) -> list:
    """Cortes calculados das palavras andam junto com elas; cortes feitos na onda (manual) nao."""
    out = []
    for c in cuts:
        if c.kind == "manual" or not bias:
            out.append(c)
            continue
        start = 0.0 if c.kind == "inicio" else min(max(0.0, c.start + bias), duration - 0.06)
        end = duration if c.kind == "fim" else min(max(start + 0.05, c.end + bias), duration)
        if end > start:
            out.append(c.model_copy(update={"start": start, "end": end}))
    return out


def load_regions(audio_dir, name: str, wav=None) -> list[Region]:
    """Trechos de voz salvos pelo pipeline; se nao houver, calcula do WAV e salva."""
    import json
    from pathlib import Path

    p = Path(audio_dir) / f"{name}.speech.json"
    if p.exists():
        try:
            return [tuple(x) for x in json.loads(p.read_text(encoding="utf-8"))["regions"]]
        except (OSError, ValueError, KeyError):
            pass
    wav = Path(wav or Path(audio_dir) / f"{name}.wav")
    if not wav.exists():
        return []
    from ..adapters.whisper import load_audio

    regions = speech_regions(load_audio(wav))
    if regions:
        p.write_text(json.dumps({"regions": regions}), encoding="utf-8")
    return regions


def voice_sync(doc, regions: Sequence[Region], env: Sequence[float] | None = None,
               rate: float = 50.0) -> tuple[float, int]:
    """Encaixa as legendas do documento na voz (no lugar). Devolve (vies corrigido, legendas movidas)."""
    before = [c.start for c in doc.captions]
    bias = estimate_bias(doc.captions, regions) if regions else 0.0
    doc.captions = snap(doc.captions, regions, env, rate)
    if bias:
        doc.cuts = shift_cuts_for_bias(doc.cuts, bias, doc.duration or max(
            (c.end for c in doc.captions), default=0.0) + 1)
    doc.voice_sync = True
    moved = sum(1 for a, b in zip(before, doc.captions, strict=False) if abs(a - b.start) > 0.02)
    return bias, moved
