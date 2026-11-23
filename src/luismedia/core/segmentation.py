"""Segmentacao de legendas por palavra (porte do gerar-legendas-v3.1.ps1).

A legenda crua do Whisper vem em frases longas, as vezes com 10 s e 3 linhas. Aqui as
palavras (com timestamp) sao reagrupadas em blocos legiveis:

1. quebra em pontuacao forte, pausa longa ou pausa natural;
2. nunca termina um bloco em palavra fraca ("de", "que", "para"...);
3. respeita duracao maxima e tamanho maximo;
4. distribui em ate duas linhas equilibradas (preferindo quebrar apos virgula);
5. ajusta duracoes: minimo legivel, maximo, sem invadir a proxima legenda;
6. velocidade de leitura: estende a legenda ate ~17 caracteres por segundo quando ha espaco;
7. intervalo minimo de 2 quadros (~0,083 s) entre legendas, para o olho perceber a troca;
8. limite opcional de palavras por legenda (cortes 9:16 no estilo CapCut: 2 a 4 palavras).

Mesmas regras e limiares da v3.1, agora testaveis e usados pelo pipeline principal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Segment, Word

WEAK_WORDS = frozenset({
    "a", "o", "as", "os", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "por", "para", "com", "que", "e", "ou", "um", "uma",
})


@dataclass(frozen=True)
class SegmentationRules:
    max_chars_line: int = 42      # legenda normal (16:9)
    max_chars_shorts: int = 32    # 9:16
    min_duration: float = 0.8
    max_duration: float = 5.0
    natural_pause: float = 0.45
    strong_pause: float = 0.75
    max_block_chars: int = 72
    split_chars: int = 55
    gap: float = 0.083        # 2 quadros a 24 fps (padrao Netflix)
    max_cps: float = 17.0     # caracteres por segundo
    max_words: int = 0        # 0 = sem limite
    min_words_split: int = 6  # palavras minimas antes de quebrar por tamanho


def normalize(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    return re.sub(r"\s+([,.!?;:])", r"\1", text)


def _last_word(text: str) -> str:
    parts = text.split()
    return re.sub(r"[^\w\-'\"]", "", parts[-1]).lower() if parts else ""


def _strong_end(text: str) -> bool:
    return bool(re.search(r"[.!?][\"']?$", text))


def _weak_end(text: str) -> bool:
    return _last_word(text) in WEAK_WORDS


def _clean_words(words: list[Word]) -> list[Word]:
    out = []
    for w in words:
        t = normalize(w.text)
        if t:
            out.append(Word(start=w.start, end=max(w.end, w.start), text=t))
    return out


def build_blocks(words: list[Word], r: SegmentationRules) -> list[list[Word]]:
    blocks: list[list[Word]] = []
    cur: list[Word] = []
    for w in words:
        if not cur:
            cur = [w]
            continue
        prev = cur[-1]
        pause = w.start - prev.end
        candidate = normalize(" ".join(x.text for x in [*cur, w]))
        duration = w.end - cur[0].start
        weak = _weak_end(prev.text)

        if _strong_end(prev.text):
            brk = True
        elif pause >= r.strong_pause and len(cur) >= 3:
            brk = True
        elif pause >= r.natural_pause and len(cur) >= 5 and not weak:
            brk = True
        elif duration >= r.max_duration:
            brk = not weak
        elif len(candidate) > r.max_block_chars and len(cur) >= r.min_words_split:
            brk = not weak
        else:
            brk = False

        if brk:
            blocks.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        blocks.append(cur)
    return blocks


def wrap_two_lines(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    words = text.split()
    best, best_score = None, float("-inf")
    for i in range(1, len(words)):
        l1, l2 = " ".join(words[:i]), " ".join(words[i:])
        if len(l1) > max_chars or len(l2) > max_chars:
            continue
        score = 100 - abs(len(l1) - len(l2))
        if re.search(r"[,;:]$", l1):
            score += 35
        if re.search(r"[.!?]$", l1):
            score += 60
        if len(l1) < 10:
            score -= 20
        if len(l2) < 10:
            score -= 20
        if score > best_score:
            best, best_score = f"{l1}\n{l2}", score
    return best if best is not None else text


def _split_long(block: list[Word], r: SegmentationRules) -> list[list[Word]]:
    """Bloco acima da duracao maxima: divide por tamanho de texto (como a v3.1)."""
    if block[-1].end - block[0].start <= r.max_duration:
        return [block]
    parts, cur = [], []
    for w in block:
        test = normalize(" ".join(x.text for x in [*cur, w]))
        if cur and len(test) > r.split_chars:
            parts.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        parts.append(cur)
    return parts


def reading_time(text: str, r: SegmentationRules) -> float:
    """Tempo minimo para ler o texto na velocidade maxima (sem contar a quebra de linha)."""
    chars = len(text.replace("\n", " ").strip())
    return max(r.min_duration, chars / r.max_cps if r.max_cps else 0)


def cps(seg: Segment) -> float:
    dur = max(0.001, seg.end - seg.start)
    return len(seg.text.replace("\n", " ").strip()) / dur


def fix_durations(caps: list[Segment], r: SegmentationRules) -> list[Segment]:
    out: list[Segment] = []
    for i, c in enumerate(caps):
        start, end = c.start, c.end
        nxt = caps[i + 1].start if i + 1 < len(caps) else None
        limit = nxt - r.gap if nxt is not None else float("inf")
        # estende ate o tempo de leitura (17 cps / duracao minima), sem invadir a proxima
        desired = start + min(r.max_duration, reading_time(c.text, r))
        end = max(end, min(desired, limit))
        end = min(end, start + r.max_duration, limit)
        end = max(end, start + 0.01)  # nunca duracao zero/negativa (a v3.1 permitia)
        out.append(Segment(start=start, end=end, text=c.text, words=c.words))
    return out


def _chunk_words(part: list[Word], max_words: int) -> list[list[Word]]:
    if max_words <= 0 or len(part) <= max_words:
        return [part]
    n = -(-len(part) // max_words)  # grupos equilibrados: 7 palavras/3 -> 3+2+2
    size, extra = divmod(len(part), n)
    out, i = [], 0
    for g in range(n):
        k = size + (1 if g < extra else 0)
        out.append(part[i:i + k])
        i += k
    return out


def _fits(text: str, max_chars: int) -> bool:
    return all(len(line) <= max_chars for line in text.split("\n"))


def _fit(part: list[Word], max_chars: int) -> list[Segment]:
    """Garante no maximo 2 linhas de max_chars. Se nao couber (comum no 9:16), divide o
    bloco em dois no ponto mais equilibrado, preferindo pontuacao. A v3.1 deixava passar
    uma linha unica longa demais nesse caso."""
    text = wrap_two_lines(normalize(" ".join(w.text for w in part)), max_chars)
    if _fits(text, max_chars) or len(part) == 1:
        return [Segment(start=part[0].start, end=part[-1].end, text=text, words=part)]
    total = len(normalize(" ".join(w.text for w in part)))
    best_i, best_score = 1, float("-inf")
    for i in range(1, len(part)):
        left = len(normalize(" ".join(w.text for w in part[:i])))
        score = -abs(total / 2 - left)
        if re.search(r"[,.;:!?]$", part[i - 1].text):
            score += 12
        if _weak_end(part[i - 1].text):
            score -= 12
        if score > best_score:
            best_i, best_score = i, score
    return _fit(part[:best_i], max_chars) + _fit(part[best_i:], max_chars)


def segment_words(words: list[Word], rules: SegmentationRules | None = None,
                  *, shorts: bool = False) -> list[Segment]:
    r = rules or SegmentationRules()
    max_chars = r.max_chars_shorts if shorts else r.max_chars_line
    caps: list[Segment] = []
    for block in build_blocks(_clean_words(words), r):
        for part in _split_long(block, r):
            for piece in _chunk_words(part, r.max_words):
                caps.extend(_fit(piece, max_chars))
    return fix_durations(caps, r)


def segment_transcript(segments: list[Segment], rules: SegmentationRules | None = None,
                       *, shorts: bool = False) -> list[Segment]:
    """Usa as palavras quando existem; sem word timestamps, devolve os segmentos com quebra de linha."""
    words = [w for s in segments for w in s.words]
    if words:
        return segment_words(words, rules, shorts=shorts)
    r = rules or SegmentationRules()
    max_chars = r.max_chars_shorts if shorts else r.max_chars_line
    caps = [Segment(start=s.start, end=s.end, text=wrap_two_lines(normalize(s.text), max_chars))
            for s in segments if normalize(s.text)]
    return fix_durations(caps, r)
