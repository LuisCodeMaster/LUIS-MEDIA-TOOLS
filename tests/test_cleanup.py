"""Limpeza da fala: pausas e vicios detectados pelas palavras do Whisper, cortes aplicados no
video e nas legendas."""

from __future__ import annotations

import pytest

from luismedia.core.cleanup import (
    CleanupSettings,
    Cut,
    TimeMap,
    detect_cuts,
    filler_kind,
    kept_spans,
    merge_detected,
    remap_captions,
    removed_seconds,
)
from luismedia.core.models import Segment, Word


def W(t: float, d: float, x: str) -> Word:  # noqa: N802
    return Word(start=t, end=t + d, text=x)


def seg(words: list[Word]) -> Segment:
    return Segment(start=words[0].start, end=words[-1].end, text=" ".join(w.text for w in words), words=words)


def test_pause_is_shortened_keeping_a_breath():
    caps = [seg([W(0, 0.4, "Olá"), W(0.45, 0.4, "turma.")]), seg([W(2.0, 0.4, "Hoje"), W(2.45, 0.4, "vamos")])]
    [c] = detect_cuts(caps, 3.0)
    assert c.kind == "pausa" and c.enabled
    assert c.start == pytest.approx(0.85 + 0.15) and c.end == pytest.approx(2.0 - 0.15)


def test_long_pause_is_kept_for_demonstrations():
    caps = [seg([W(0, 0.4, "Olha")]), seg([W(9.0, 0.4, "isso")])]
    assert detect_cuts(caps, 10.0, CleanupSettings(max_pause_s=6)) == []


def test_pause_with_sound_comes_unchecked():
    caps = [seg([W(0, 0.5, "um")]), seg([W(2.0, 0.5, "dois")])]
    env = [0.8] * 25 + [0.6] * 75 + [0.8] * 25  # 50/s: musica alta na pausa
    [c] = detect_cuts(caps, 2.5, envelope=env)
    assert not c.enabled and "com som" in c.label


@pytest.mark.parametrize("words,i,kind", [
    ([W(0, .3, "isso"), W(.6, .7, "éé..."), W(1.6, .3, "aqui")], 1, "strong"),
    ([W(0, .3, "isso"), W(.35, .4, "hum"), W(.8, .3, "aqui")], 1, "strong"),
    ([W(0, .3, "isso"), W(.32, .1, "é"), W(.45, .4, "importante")], 1, None),   # verbo "é"
    ([W(0, .3, "certo,"), W(.6, .2, "né?"), W(1.2, .3, "agora")], 1, "soft"),
    ([W(0, .3, "eu"), W(.32, .2, "tipo"), W(.55, .3, "gosto")], 1, None),       # "tipo" de verdade
    ([W(0, .3, "era,"), W(.5, .25, "tipo,"), W(1.0, .3, "enorme")], 1, "soft"),
])
def test_filler_kinds(words, i, kind):
    assert filler_kind(words, i) == kind


def test_filler_cut_swallows_surrounding_silence():
    caps = [seg([W(0, 0.4, "Olá"), W(1.0, 0.6, "éé..."), W(2.2, 0.4, "hoje")])]
    cuts = detect_cuts(caps, 3.0)
    vicio = next(c for c in cuts if c.kind == "vicio")
    assert vicio.start == pytest.approx(0.55) and vicio.end == pytest.approx(2.05)
    assert [s.model_dump() for s in kept_spans(cuts, 3.0)] == [
        {"start": 0.0, "end": pytest.approx(0.55)}, {"start": pytest.approx(2.05), "end": 3.0}]


def test_soft_fillers_suggested_but_unchecked():
    caps = [seg([W(0, .3, "certo,"), W(.6, .2, "né?"), W(1.2, .3, "agora")])]
    vicios = [c for c in detect_cuts(caps, 2.0) if c.kind == "vicio"]
    c = next(c for c in vicios if "né" in c.label)
    assert not c.enabled and "talvez" in c.label
    assert not any(c.enabled for c in vicios)


def test_time_map_and_removed_seconds():
    cuts = [Cut(start=1, end=2), Cut(start=1.5, end=3), Cut(start=5, end=6, enabled=False)]
    tm = TimeMap(cuts)
    assert tm(0.5) == 0.5 and tm(1.5) == 1.0 and tm(4) == 2.0 and tm(5.5) == 3.5
    assert removed_seconds(cuts) == pytest.approx(2.0)


def test_remap_drops_cut_words_and_shifts_times():
    caps = [seg([W(0, 0.4, "Olá"), W(0.5, 0.4, "turma,"), W(1.0, 0.6, "éé..."), W(2.2, 0.4, "hoje")]),
            seg([W(4.0, 0.4, "Vamos"), W(4.5, 0.5, "começar.")])]
    cuts = [Cut(start=0.95, end=2.1, kind="vicio"), Cut(start=2.8, end=3.8)]
    a, b = remap_captions(caps, cuts)
    assert a.text == "Olá turma, hoje" and "éé" not in a.text
    assert a.words[-1].start == pytest.approx(2.2 - 1.15)
    assert b.start == pytest.approx(4.0 - 1.15 - 1.0) and b.text == caps[1].text


def test_remap_removes_caption_that_was_only_filler():
    caps = [seg([W(0, 0.5, "Hum...")]), seg([W(1, 0.4, "Oi")])]
    out = remap_captions(caps, [Cut(start=0, end=0.6, kind="vicio")])
    assert [c.text for c in out] == ["Oi"] and out[0].start == pytest.approx(0.4)


def test_new_detection_keeps_manual_cuts():
    old = [Cut(start=1, end=2, kind="manual"), Cut(start=3, end=4)]
    got = merge_detected(old, [Cut(start=5, end=6)])
    assert [(c.start, c.kind) for c in got] == [(1, "manual"), (5, "pausa")]


def test_cut_validation():
    with pytest.raises(ValueError):
        Cut(start=2, end=1)


def test_whisper_prompt_asks_for_fillers():
    from luismedia.adapters.whisper import vocabulary_kwargs
    from luismedia.core.config import WhisperConfig

    kw = vocabulary_kwargs(WhisperConfig(vocabulary=["LGPD"]), fillers=True)
    assert "ãh" in kw["initial_prompt"] and "LGPD" in kw["initial_prompt"] and kw["hotwords"] == "LGPD"
    assert "hotwords" not in vocabulary_kwargs(WhisperConfig(), fillers=True)


def test_envelope_from_pcm():
    np = pytest.importorskip("numpy")
    from luismedia.core.cleanup import envelope_from_pcm

    sig = np.concatenate([np.zeros(8000), np.full(8000, 8000, dtype=np.int16)])
    env = envelope_from_pcm(sig.astype(np.int16), 16000, 50)
    assert len(env) == 50 and env[0] == 0 and env[-1] > 0.5


# ------------------------------------------------------------------ regravacoes
def _speech(spec: str) -> list[Segment]:
    """'Hoje vamos |0.6 hoje vamos ver' -> palavras de 0,3 s; |x = pausa extra de x s."""
    ws, t = [], 0.0
    for tok in spec.split():
        if tok.startswith("|"):
            t += float(tok[1:])
            continue
        ws.append(W(t, 0.3, tok))
        t += 0.35
    return [seg(ws)]


@pytest.mark.parametrize("spec,attempt,enabled", [
    ("Então a função quadrática é |0.5 a função quadrática é definida assim.", "a função quadrática é", True),
    ("A derivada de x é 3x, não, a derivada de x é 2x.", "A derivada de x é 3x, não", True),
    ("Hoje vamos ver |0.6 hoje vamos ver funções.", "Hoje vamos ver", True),
    ("Agora vamos calcular o delta, éé... agora vamos calcular o delta certo.", "Agora vamos calcular o delta, éé...", True),
])
def test_retakes_found(spec, attempt, enabled):
    from luismedia.core.cleanup import detect_retakes

    [c] = detect_retakes(_speech(spec))
    assert c.kind == "repeticao" and attempt in c.label and c.enabled == enabled
    out = remap_captions(_speech(spec), [c])
    assert out[0].text.lower().count(attempt.split()[1].lower()) == 1  # sobrou so a ultima tentativa


@pytest.mark.parametrize("spec", [
    "a função f de x e a função g de x são iguais.",
    "Isso é muito, muito importante.",
    "x mais 2 vezes x mais 2 dá isso.",
    "Primeiro passo, segundo passo, terceiro passo.",
])
def test_no_false_retakes(spec):
    from luismedia.core.cleanup import detect_retakes

    assert detect_retakes(_speech(spec)) == []


def test_new_detection_keeps_text_cuts():
    old = [Cut(start=1, end=2, kind="texto"), Cut(start=3, end=4, kind="repeticao")]
    assert [c.kind for c in merge_detected(old, [])] == ["texto"]


# ------------------------------------------------------------------ relatorio
def test_teacher_report_numbers_and_html():
    from luismedia.core.report import auto_tips, build_report, render_html, summary_line

    caps = _speech("Hoje vamos ver |0.6 hoje vamos ver funções. É... basicamente, hum, funções servem pra quê? "
                   "Basicamente basicamente basicamente basicamente basicamente.")
    cuts = detect_cuts(caps, 30.0)
    r = build_report(caps, cuts, 30.0)
    assert r["words"] == len(caps[0].words) and r["wpm"] > 100
    assert r["fillers"].get("hum") == 1 and len(r["retakes"]) == 1
    assert r["crutches"].get("basicamente", 0) >= 5 and r["questions"] == 1
    assert set(r["scores"]) == {"ritmo", "fluencia", "clareza", "engajamento", "geral"}
    r["tips"] = auto_tips(r)
    assert any("basicamente" in t for t in r["tips"])
    page = render_html(r, "Aula <1>")
    assert "Relatório da aula" in page and "Aula &lt;1&gt;" in page and "<script" not in page
    assert "palavras/min" in summary_line(r)
