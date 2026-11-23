"""Fala sintetica (vogais com formantes, ritmo de silabas) para testar o detector de voz sem
precisar de gravacao de verdade. So numpy."""

from __future__ import annotations

import numpy as np

SR = 16000
VOWELS = [((700, 110), (1220, 120), (2600, 160)), ((300, 60), (2300, 100), (3000, 150)),
          ((500, 80), (900, 90), (2400, 150)), ((350, 70), (800, 80), (2300, 140))]


def _vowel(dur: float, f0: float, formants) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    ph = np.cumsum(f0 * (1 + 0.05 * np.sin(2 * np.pi * 3 * t)) / SR)
    src = (np.diff(np.floor(ph), prepend=0) > 0).astype(float)
    k = np.arange(int(0.03 * SR)) / SR
    ir = sum(np.exp(-np.pi * bw * k) * np.sin(2 * np.pi * fc * k) for fc, bw in formants)
    y = np.convolve(src, ir)[:n]
    env = np.minimum(1, np.minimum(t / 0.02, (dur - t) / 0.03))
    return y / (np.max(np.abs(y)) or 1) * env


def speech_audio(spans, total: float, music: float = 0.0, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = np.zeros(int(total * SR))
    for a, b in spans:
        parts, t = [], 0.0
        while t < b - a:
            d = rng.uniform(0.12, 0.25)
            parts.append(_vowel(d, rng.uniform(100, 140), VOWELS[rng.integers(4)]))
            g = rng.uniform(0.02, 0.06)
            parts.append(np.zeros(int(g * SR)))
            t += d + g
        s = np.concatenate(parts)[: int((b - a) * SR)]
        x[int(a * SR):int(a * SR) + len(s)] += 0.5 * s
    if music:
        t = np.arange(len(x)) / SR
        x += music * sum(np.sin(2 * np.pi * f * t) for f in (220, 277, 330)) / 3 * (0.6 + 0.4 * np.sin(np.pi * t))
    return x.astype(np.float32)
