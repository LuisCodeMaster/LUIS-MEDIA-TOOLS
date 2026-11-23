"""Sincronia (encaixe na voz) e ritmo das legendas."""

from __future__ import annotations

import pytest

from luismedia.core.models import Segment, Word
from luismedia.core.segmentation import SegmentationRules, segment_words
from luismedia.core.sync import LEAD_S, resegment, rules_for_pace, shift_all, snap_to_speech

RATE = 50


def env_with_speech(spans, total=10.0, loud=0.6):
    env = [0.0] * int(total * RATE)
    for a, b in spans:
        for i in range(int(a * RATE), int(b * RATE)):
            env[i] = loud
    return env


def W(t, d, x):  # noqa: N802
    return Word(start=t, end=t + d, text=x)


def seg(ws):
    return Segment(start=ws[0].start, end=ws[-1].end + 0.3, text=" ".join(w.text for w in ws), words=ws)


def test_early_caption_is_moved_to_the_voice():
    # o Whisper marcou 2.0 s, mas a voz so comeca em 2.5 s
    caps = [seg([W(0.2, 0.5, "Oi"), W(0.75, 0.5, "turma.")]), seg([W(2.0, 0.9, "Hoje"), W(3.0, 0.4, "vamos")])]
    env = env_with_speech([(0.2, 1.3), (2.5, 3.5)])
    a, b = snap_to_speech(caps, env)
    assert a.start == caps[0].start  # ja estava certa: nao mexe
    assert b.start == pytest.approx(2.5 - LEAD_S, abs=0.03)
    assert b.words[0].start == pytest.approx(2.5 - LEAD_S, abs=0.03) and b.words[1].start == 3.0


def test_snap_never_moves_backwards_or_without_audio():
    caps = [seg([W(1.0, 0.5, "certo")])]
    assert snap_to_speech(caps, None) == caps
    env = env_with_speech([(0.5, 2.0)])  # voz ja tinha comecado
    assert snap_to_speech(caps, env)[0].start == 1.0


def test_paces_change_block_size():
    words = [W(i * 0.3, 0.25, f"palavra{i}") for i in range(30)]
    base = SegmentationRules()
    fast = segment_words(words, rules_for_pace(base, "rapido"))
    normal = segment_words(words, rules_for_pace(base, "padrao"))
    slow = segment_words(words, rules_for_pace(base, "devagar"))
    assert len(fast) > len(normal) and len(slow) <= len(normal)
    assert sum(c.end - c.start for c in slow) / len(slow) >= sum(c.end - c.start for c in normal) / len(normal)
    assert max(c.end - c.start for c in fast) <= 2.7
    assert rules_for_pace(base, "padrao") == base


def test_resegment_keeps_corrected_text_and_shift():
    caps = [seg([W(0, 0.3, "Olá"), W(0.35, 0.3, "Whisper"), W(0.7, 0.3, "turma.")])]
    out = resegment(caps, rules_for_pace(SegmentationRules(), "rapido"))
    assert " ".join(c.text for c in out).replace("\n", " ") == "Olá Whisper turma."
    moved = shift_all(out, 0.25)
    assert moved[0].start == pytest.approx(out[0].start + 0.25)
    assert moved[0].words[0].start == pytest.approx(0.25)
    assert shift_all(out, -5)[0].start == 0.0


def test_pipeline_snaps_whisper_early_start(tmp_path, lesson_video):
    """lesson_video: voz em 4.5 s; o Whisper falso diz 4.1 s. A legenda tem que sair em ~4.45 s."""
    pytest.importorskip("numpy")
    from pathlib import Path

    from luismedia.core.captions import CaptionDoc
    from luismedia.core.config import Settings
    from luismedia.core.models import Transcript
    from luismedia.pipeline.runner import Pipeline

    class EarlyWhisper:
        def transcribe(self, audio, duration, on_progress=None):
            a = [W(0.05, .5, "Bom"), W(0.6, .5, "dia.")]
            b = [W(4.1, .9, "Vamos"), W(5.1, .5, "lá.")]
            return Transcript(language="pt", duration=duration, model="f", device="cpu",
                              segments=[seg(a), seg(b)])

    s = Settings(render={"encoder": "libx264", "hardsub": False}, llm={"enabled": False},
                 slides={"enabled": False, "handout": False}, audio={"master": False},
                 cleanup={"enabled": False}, subtitles={"pace": "rapido"})
    p = Pipeline(s)
    p.whisper = EarlyWhisper()
    [r] = p.run([lesson_video], tmp_path / "out")
    assert r.ok, r.error
    doc = CaptionDoc.load(Path(r.outputs["captions"]))
    second = next(c for c in doc.captions if "Vamos" in c.text)
    assert 4.35 < second.start < 4.5 and doc.pace == "rapido"
