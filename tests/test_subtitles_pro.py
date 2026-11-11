"""Legendas profissionais: velocidade de leitura, intervalo, estilos, revisao e vocabulario."""

from __future__ import annotations

from pathlib import Path

import pytest

from luismedia.core.captions import CaptionDoc, apply_replacements, realign_words
from luismedia.core.config import Settings, WhisperConfig
from luismedia.core.models import Segment, Transcript, Word
from luismedia.core.segmentation import SegmentationRules, cps, segment_words
from luismedia.core.style import PRESETS_H, PRESETS_V, SubtitleStyle, ass_color, events, header

from .conftest import needs_ffmpeg, needs_libass
from .test_features import words_from


# ------------------------------------------------------------------ regras
def test_reading_speed_extends_fast_captions_when_there_is_room():
    # 40 caracteres falados em 1,2 s (33 cps) com 3 s livres depois
    ws = words_from("Velocidade de leitura precisa ser confortavel.", step=0.17)
    [cap] = segment_words(ws, SegmentationRules(max_cps=17))
    assert cps(cap) <= 17.05


def test_reading_speed_never_invades_next_caption():
    ws = words_from("Primeira frase bem longa falada muito rapido. Segunda.", step=0.08)
    r = SegmentationRules()
    caps = segment_words(ws, r)
    for a, b in zip(caps, caps[1:], strict=False):
        assert b.start - a.end >= r.gap - 1e-6


def test_gap_is_two_frames_by_default():
    assert SegmentationRules().gap == pytest.approx(0.083)


def test_max_words_splits_into_balanced_groups():
    ws = words_from("um dois tres quatro cinco seis sete", step=0.3)
    caps = segment_words(ws, SegmentationRules(max_words=3), shorts=True)
    assert [len(c.text.split()) for c in caps] == [3, 2, 2]
    assert all(c.words for c in caps)  # palavras guardadas para o karaoke


# ------------------------------------------------------------------ estilos
def test_ass_color_is_bgr_with_inverted_alpha():
    assert ass_color("#FFE600") == "&H0000E6FF"
    assert ass_color("#000000", 0.6) == "&H66000000"


def test_invalid_color_is_rejected():
    with pytest.raises(ValueError):
        SubtitleStyle(color="amarelo")


def test_box_uses_border_style_4_and_sizes_scale_with_video():
    h = header(SubtitleStyle(box=True, size=5), 1080, 1920)
    style_line = next(line for line in h.splitlines() if line.startswith("Style:"))
    fields = style_line.split(",")
    assert fields[15] == "4" and fields[2] == "54"  # 5% do lado menor (1080)


def test_karaoke_creates_one_event_per_word_with_highlight():
    seg = Segment(start=0, end=2, text="tres palavras aqui",
                  words=[Word(start=0, end=0.5, text="tres"), Word(start=0.6, end=1.1, text="palavras"),
                         Word(start=1.2, end=1.9, text="aqui")])
    ev = events([seg], PRESETS_V["Destaque verde"])
    assert len(ev) == 3
    assert "\\c&H0014FF39&}PALAVRAS" in ev[1]  # maiusculas + verde na palavra atual


def test_reveal_hides_future_words():
    seg = Segment(start=0, end=2, text="a b c", words=[Word(start=0, end=0.5, text="a"),
                                                       Word(start=0.6, end=1, text="b"),
                                                       Word(start=1.2, end=1.9, text="c")])
    first = events([seg], PRESETS_V["Karaokê"])[0]
    assert first.count("\\alpha&HFF&") == 2


def test_presets_are_valid_settings():
    for p in [*PRESETS_H.values(), *PRESETS_V.values()]:
        Settings.model_validate({"subtitles": {"style_h": p.model_dump(), "style_v": p.model_dump()}})


@needs_libass
def test_style_preview_renders_png(tmp_path):
    from luismedia.stages.media import render_style_preview

    out = render_style_preview(PRESETS_V["CapCut amarelo"], tmp_path / "p.png", width=270, height=480)
    assert out.exists() and out.stat().st_size > 1000


# ------------------------------------------------------------------ texto
def test_replacements_only_whole_words_case_insensitive():
    assert apply_replacements("o wisper e o Wisper2", {"wisper": "Whisper"}) == "o Whisper e o Wisper2"


def test_realign_keeps_times_when_word_count_matches():
    seg = Segment(start=0, end=1, text="ola mundo", words=[Word(start=0, end=0.4, text="ola"),
                                                           Word(start=0.5, end=1, text="mundo")])
    assert realign_words(seg, "Olá mundo!").words[1].start == 0.5
    assert len(realign_words(seg, "olá a todos").words) == 3


def test_vocabulary_goes_to_whisper():
    from luismedia.adapters.whisper import vocabulary_kwargs

    kw = vocabulary_kwargs(WhisperConfig(vocabulary=["Vygotsky", " LGPD ", "Vygotsky"]))
    assert kw["hotwords"] == "Vygotsky, LGPD" and "Vygotsky" in kw["initial_prompt"]
    assert vocabulary_kwargs(WhisperConfig()) == {}


# ------------------------------------------------------------------ revisao no pipeline
class CountingWhisper:
    def __init__(self):
        self.calls = 0

    def transcribe(self, audio, duration, on_progress=None):
        self.calls += 1
        words = [Word(start=0.5, end=0.9, text="Bem-vindos"), Word(start=1.0, end=1.3, text="ao"),
                 Word(start=1.4, end=2.0, text="wisper.")]
        return Transcript(language="pt", duration=duration, model="fake", device="cpu",
                          segments=[Segment(start=0.5, end=2.0, text="Bem-vindos ao wisper.", words=words)])


@needs_ffmpeg
@needs_libass
def test_review_flow_pauses_then_uses_edited_text(tmp_path, lesson_video):
    from luismedia.pipeline.runner import Pipeline, captions_edited

    base = {"render": {"encoder": "libx264", "crf": 32}, "autocut": {"enabled": False},
            "llm": {"enabled": False}, "slides": {"enabled": False, "handout": False},
            "audio": {"master": False}}
    s = Settings.model_validate({**base, "subtitles": {"review": True, "replacements": {"wisper": "Whisper"}}})
    whisper = CountingWhisper()
    p = Pipeline(s)
    p.whisper = whisper
    [r] = p.run([lesson_video], tmp_path / "out")
    assert r.ok and r.needs_review and "video_legendado" not in r.outputs

    cap_path = Path(r.outputs["captions"])
    doc = CaptionDoc.load(cap_path)
    assert "Whisper" in doc.captions[0].text  # substituicao automatica aplicada
    doc.captions[0] = realign_words(doc.captions[0], "Bem-vindos ao curso de Whisper!")
    doc.approved = True
    doc.save(cap_path)
    captions_edited(cap_path.parent.parent)

    p2 = Pipeline(s)
    p2.whisper = whisper
    [r2] = p2.run([lesson_video], tmp_path / "out")
    assert r2.ok and not r2.needs_review and "video_legendado" in r2.outputs
    assert whisper.calls == 1  # nao transcreveu de novo
    assert "curso de Whisper" in Path(r2.outputs["srt"]).read_text(encoding="utf-8")


@needs_ffmpeg
@needs_libass
def test_changing_style_redoes_only_subtitle_stages(tmp_path, lesson_video):
    from luismedia.pipeline.runner import Pipeline

    base = {"render": {"encoder": "libx264", "crf": 32}, "autocut": {"enabled": False},
            "llm": {"enabled": False}, "slides": {"enabled": False, "handout": False},
            "audio": {"master": False}}
    whisper = CountingWhisper()
    p = Pipeline(Settings.model_validate(base))
    p.whisper = whisper
    p.run([lesson_video], tmp_path / "out")
    events_seen = []
    s2 = Settings.model_validate({**base, "subtitles": {"style_h": PRESETS_H["Amarelo TV"].model_dump()}})
    p2 = Pipeline(s2, listeners=[events_seen.append])
    p2.whisper = whisper
    p2.run([lesson_video], tmp_path / "out")
    ran = {e.stage for e in events_seen if e.status == "done"}
    assert ran == {"legendas", "hardsub"} and whisper.calls == 1
