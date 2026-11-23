"""Sincronia (encaixe na voz) e ritmo das legendas."""

from __future__ import annotations

from pathlib import Path

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


# ------------------------------------------------------------------ audio que comeca depois da imagem
def _shifted_video(tmp_path, lesson_video, delay=0.7):
    import subprocess

    from luismedia.adapters import ffmpeg as ff

    out = tmp_path / "atrasado.mp4"
    subprocess.run([ff.find_binary("ffmpeg"), "-v", "error", "-y", "-i", str(lesson_video), "-itsoffset", str(delay),
                    "-i", str(lesson_video), "-map", "0:v", "-map", "1:a", "-c", "copy", str(out)], check=True)
    return out


class EnergyWhisper:
    """Whisper falso honesto: poe uma palavra onde o WAV realmente tem som."""

    def transcribe(self, audio, duration, on_progress=None):
        from luismedia.core.cleanup import read_envelope_wav
        from luismedia.core.models import Transcript

        env = read_envelope_wav(audio)
        on = next(i for i, v in enumerate(env) if v > 0.05) / 50
        w = W(on, 0.8, "Olá")
        return Transcript(language="pt", duration=duration, model="f", device="cpu", segments=[seg([w])])


def test_audio_delay_in_file_keeps_captions_in_sync(tmp_path, lesson_video):
    pytest.importorskip("numpy")
    from luismedia.adapters import ffmpeg as ff
    from luismedia.core.captions import CaptionDoc
    from luismedia.core.config import Settings
    from luismedia.pipeline.runner import Pipeline

    vid = _shifted_video(tmp_path, lesson_video, 0.7)
    assert ff.probe(vid).audio_offset == pytest.approx(0.7, abs=0.06)
    s = Settings(render={"encoder": "libx264", "hardsub": False}, llm={"enabled": False},
                 slides={"enabled": False, "handout": False}, audio={"master": False}, cleanup={"enabled": False})
    p = Pipeline(s)
    p.whisper = EnergyWhisper()
    [r] = p.run([vid], tmp_path / "out")
    assert r.ok, r.error
    doc = CaptionDoc.load(Path(r.outputs["captions"]))
    assert doc.captions[0].start == pytest.approx(0.7, abs=0.08)  # a voz aparece em 0,7 s no video
    assert doc.av_offset == pytest.approx(0.7, abs=0.06)


def test_old_results_are_repaired_once(tmp_path, lesson_video):
    pytest.importorskip("numpy")
    import subprocess

    from luismedia.adapters import ffmpeg as ff
    from luismedia.core.captions import CaptionDoc
    from luismedia.core.cleanup import Cut
    from luismedia.pipeline.runner import repair_av_offset

    vid = _shifted_video(tmp_path, lesson_video, 0.7)
    out = tmp_path / "out" / "atrasado"
    (out / "audio").mkdir(parents=True)
    (out / "legendas").mkdir()
    wav = out / "audio" / "atrasado.wav"  # do jeito antigo: sem o atraso
    subprocess.run([ff.find_binary("ffmpeg"), "-v", "error", "-y", "-i", str(vid), "-vn", "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", str(wav)], check=True)
    capp = out / "legendas" / "atrasado.captions.json"
    CaptionDoc(video=str(vid), width=320, height=240, duration=12,
               captions=[seg([W(0.0, 0.8, "Olá")])], cuts=[Cut(start=3.0, end=4.4)]).save(capp)
    info = ff.probe(vid)
    assert repair_av_offset(info, out, "atrasado") == pytest.approx(0.7, abs=0.06)
    doc = CaptionDoc.load(capp)
    assert doc.captions[0].start == pytest.approx(0.7, abs=0.06) and doc.cuts[0].start == pytest.approx(3.7, abs=0.06)
    assert repair_av_offset(info, out, "atrasado") == 0.0  # so uma vez
    assert CaptionDoc.load(capp).captions[0].start == pytest.approx(doc.captions[0].start)
