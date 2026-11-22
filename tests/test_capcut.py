"""Recursos estilo CapCut: animacoes, caixa na palavra, gradiente, palavras-chave, emojis,
posicao livre e modelos do usuario."""

from __future__ import annotations

import json

import pytest

from luismedia.core.captions import CaptionDoc
from luismedia.core.config import Encoder
from luismedia.core.models import Segment, Word
from luismedia.core.style import (
    PRESETS_V,
    SubtitleStyle,
    emoji_for,
    emoji_overlay,
    emoji_plan,
    events,
    header,
    norm_word,
)

from .conftest import needs_ffmpeg, needs_libass


def seg3(text: str = "vamos ganhar dinheiro", start: float = 0.0) -> Segment:
    ws = text.split()
    return Segment(start=start, end=start + 2, text=text,
                   words=[Word(start=start + i * 0.6, end=start + i * 0.6 + 0.5, text=w) for i, w in enumerate(ws)])


# ------------------------------------------------------------------ animacoes
@pytest.mark.parametrize("anim,tag", [("bounce", "\\t("), ("slide", "\\move("), ("fade", "\\fad(")])
def test_entrance_animations_only_on_first_event(anim, tag):
    ev = events([seg3()], SubtitleStyle(animation=anim, highlight="color"))
    assert tag in ev[0]
    assert all(tag not in e for e in ev[1:])  # trocar a palavra falada nao reanima


def test_typewriter_reveals_characters_progressively():
    ev = events([seg3("ola mundo")], SubtitleStyle(animation="typewriter"))
    assert len(ev) > 3
    hidden = [e.count("\\alpha&HFF&") for e in ev]
    assert hidden[0] >= 1 and hidden[-1] == 0  # comeca escondido, termina inteiro


# ------------------------------------------------------------------ caixa na palavra
def test_box_highlight_adds_box_style_and_one_box_per_word():
    s = SubtitleStyle(highlight="box", highlight_color="#7C3AED")
    h = header(s, 1080, 1920)
    assert any(line.startswith("Style: Box,") for line in h.splitlines())
    ev = events([seg3()], s)
    boxes = [e for e in ev if ",Box," in e]
    assert len(boxes) == 3  # uma caixa para cada palavra falada
    for e in boxes:
        assert "\\3a&HFF&" in e  # so a palavra atual tem caixa visivel
        assert e.startswith("Dialogue: 0,")


# ------------------------------------------------------------------ cores
def test_gradient_uses_clip_bands():
    ev = events([Segment(start=0, end=1, text="fogo")], SubtitleStyle(gradient=True, gradient_color="#FF0000"))
    clipped = [e for e in ev if "\\clip(" in e]
    assert len(clipped) >= 4


def test_two_alternating_colors():
    s = SubtitleStyle(alt_colors=True, color="#FFFFFF", color2="#00FF00")
    a = events([Segment(start=0, end=1, text="um")], s)[0]
    b = events([Segment(start=0, end=1, text="um"), Segment(start=1.2, end=2, text="dois")], s)[1]
    assert "&H0000FF00&" in b and "&H0000FF00&" not in a


# ------------------------------------------------------------------ palavras-chave
def test_keywords_get_color_and_scale_ignoring_accents_and_case():
    s = SubtitleStyle(keywords=True, keyword_color="#22D3EE", keyword_scale=130)
    ev = events([Segment(start=0, end=1, text="Aprenda Funções hoje")], s, keywords=["funcoes"])[0]
    assert "{\\fs70\\c&H00EED322&}Funções" in ev  # 54 px * 130%
    assert norm_word("Funções!") == "funcoes"


def test_keywords_off_ignores_list():
    ev = events([Segment(start=0, end=1, text="funcoes")], SubtitleStyle(), keywords=["funcoes"])[0]
    assert "\\fs" not in ev.split("}", 1)[1]


def test_keyword_list_model_and_caption_doc(tmp_path):
    from luismedia.core.models import KeywordList

    assert KeywordList.model_validate({"keywords": ["Python"]}).keywords == ["Python"]
    doc = CaptionDoc(video="v.mp4", width=1920, height=1080, captions=[seg3()], keywords=["Python"])
    p = tmp_path / "a.captions.json"
    doc.save(p)
    assert CaptionDoc.load(p).keywords == ["Python"]


def test_ai_keywords_uses_schema():
    from luismedia.stages import ai

    class FakeLLM:
        def generate_model(self, prompt, schema, **kw):
            return schema.model_validate({"keywords": ["função", "variável"]})

    assert ai.keywords(FakeLLM(), "texto", 1000) == ["função", "variável"]


# ------------------------------------------------------------------ emojis
def test_emoji_words_map_to_bundled_pngs():
    assert emoji_for("Dinheiro!") == "1f4b0"
    assert emoji_for("ideias") == "1f4a1"
    assert emoji_for("cadeira") is None


def test_emoji_plan_respects_gap_and_position():
    s = SubtitleStyle(emojis=True, position="bottom")
    segs = [seg3("vamos ganhar dinheiro", 0), seg3("mais dinheiro", 2.2), seg3("tenho uma ideia", 6)]
    plan = emoji_plan(segs, s, 1080, 1920)
    assert [p.start for p in plan] == [0, 6]  # o 2o fica de fora (muito perto)
    assert all(p.png.exists() for p in plan)
    assert all(0 <= p.y < 1920 - p.size for p in plan)
    assert emoji_plan(segs, SubtitleStyle(), 1080, 1920) == []


def test_emoji_overlay_groups_by_emoji():
    s = SubtitleStyle(emojis=True)
    segs = [seg3("dinheiro", 0), seg3("ideia", 5), seg3("dinheiro", 10)]
    plan = emoji_plan(segs, s, 1080, 1920)
    inputs, graph = emoji_overlay(plan, "a", "b", 1)
    assert inputs.count("-i") == 2  # 2 emojis diferentes, 3 aparicoes
    assert graph.endswith("[b]") and "[1:v]" in graph and "[2:v]" in graph
    assert emoji_overlay([], "a", "b", 1) == ([], "[a]null[b]")


# ------------------------------------------------------------------ posicao livre
def test_custom_position_uses_pos_tag_at_percent():
    ev = events([Segment(start=0, end=1, text="oi")], SubtitleStyle(position="custom", pos_x=25, pos_y=40),
                width=1000, height=2000)[0]
    assert "\\an5" in ev and "\\pos(250,800)" in ev


def test_new_presets_exist():
    for name in ("Marca-texto", "Gradiente fogo", "Duas cores", "Máquina de escrever"):
        assert name in PRESETS_V


# ------------------------------------------------------------------ render real
@needs_libass
@pytest.mark.parametrize("name", ["Marca-texto", "Gradiente fogo", "Duas cores", "Máquina de escrever"])
def test_new_presets_render(tmp_path, name):
    from luismedia.stages.media import render_style_preview

    out = render_style_preview(PRESETS_V[name], tmp_path / "p.png", width=270, height=480)
    assert out.exists() and out.stat().st_size > 1000


@needs_ffmpeg
@needs_libass
def test_burn_with_emojis(tmp_path, lesson_video):
    from luismedia.adapters import ffmpeg as ff
    from luismedia.core.style import write_styled_ass
    from luismedia.stages.media import burn_subtitles

    info = ff.probe(lesson_video)
    s = SubtitleStyle(emojis=True, keywords=True)
    segs = [seg3("vamos ganhar dinheiro", 0.5), seg3("tenho uma ideia", 5)]
    ass = write_styled_ass(segs, tmp_path / "a.ass", s, info.width, info.height, keywords=["dinheiro"])
    plan = emoji_plan(segs, s, info.width, info.height, ["dinheiro"])
    assert len(plan) == 2
    work = tmp_path / "w"
    work.mkdir()
    out = burn_subtitles(info, ass, tmp_path / "out.mp4", encoder=Encoder.CPU, crf=30, work=work, emojis=plan)
    got = ff.probe(out)
    assert abs(got.duration - info.duration) < 0.5 and got.has_audio


# ------------------------------------------------------------------ modelos do usuario
def test_user_presets_roundtrip(tmp_path, monkeypatch):
    from luismedia.gui import style_page

    monkeypatch.setattr(style_page.state, "data_dir", lambda: tmp_path)
    style_page.save_user_presets({"h": {}, "v": {"Cliente X": PRESETS_V["Neon"]}})
    got = style_page.load_user_presets()
    assert got["v"]["Cliente X"] == PRESETS_V["Neon"] and got["h"] == {}
    raw = json.loads((tmp_path / "estilos.json").read_text(encoding="utf-8"))
    raw["v"]["quebrado"] = {"color": "nao-e-cor"}
    (tmp_path / "estilos.json").write_text(json.dumps(raw), encoding="utf-8")
    assert set(style_page.load_user_presets()["v"]) == {"Cliente X"}  # ignora so o invalido


# ------------------------------------------------------------------ previa animada
def test_preview_segments_window_and_sample():
    from luismedia.stages.media import preview_segments

    segs = [seg3("um dois tres", 1), seg3("quatro cinco", 10)]
    got = preview_segments(SubtitleStyle(), 1080, 1920, 2.0, 4.0, segs)
    assert len(got) == 1 and got[0].start == 0 and got[0].end == pytest.approx(1.0)
    assert preview_segments(SubtitleStyle(), 1080, 1920, 0, 4, None)[0].text.startswith("Hoje")


@needs_ffmpeg
@needs_libass
def test_render_style_clip_frames(tmp_path, lesson_video):
    from luismedia.stages.media import PREVIEW_FPS, render_style_clip

    s = PRESETS_V["Marca-texto"]
    segs = [seg3("vamos ganhar dinheiro", 4.6)]
    frames = render_style_clip(s, tmp_path / "c", width=180, height=320, background=lesson_video,
                               start=5.0, duration=2.0, segments=segs, keywords=["dinheiro"])
    assert abs(len(frames) - 2 * PREVIEW_FPS) <= 2
    again = render_style_clip(s, tmp_path / "c", width=180, height=320, duration=1.0)  # sem video
    assert abs(len(again) - PREVIEW_FPS) <= 2  # quadros antigos apagados
