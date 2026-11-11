"""Segmentacao de legendas, IA (com Ollama falso), apostila e PDF."""

from __future__ import annotations

import io
import json

import pytest

from luismedia.adapters.ollama import OllamaClient
from luismedia.core.config import LLMConfig
from luismedia.core.models import Quiz, Segment, SlideFrame, Transcript, Word
from luismedia.core.segmentation import (
    SegmentationRules,
    segment_transcript,
    segment_words,
    wrap_two_lines,
)
from luismedia.stages import ai, editorial


def words_from(text: str, start: float = 0.0, step: float = 0.3, pause_after: dict | None = None):
    out, t = [], start
    for i, w in enumerate(text.split()):
        out.append(Word(start=t, end=t + step * 0.8, text=w))
        t += step + (pause_after or {}).get(i, 0)
    return out


# ------------------------------------------------------------------ segmentacao
def test_breaks_on_strong_punctuation():
    caps = segment_words(words_from("Bom dia turma. Hoje vamos estudar funcoes."))
    assert [c.text.replace("\n", " ") for c in caps] == ["Bom dia turma.", "Hoje vamos estudar funcoes."]


def test_never_ends_block_on_weak_word():
    # pausa natural (0.5 s) logo depois de "de": nao pode quebrar ali
    ws = words_from("vamos falar sobre o conceito de derivada agora", pause_after={5: 0.5})
    caps = segment_words(ws)
    assert len(caps) == 1 and caps[0].text.replace("\n", " ").endswith("de derivada agora")


def test_lines_respect_max_chars_and_two_lines():
    long = " ".join(["palavra"] * 40)
    for c in segment_words(words_from(long, step=0.1)):
        lines = c.text.split("\n")
        assert len(lines) <= 2 and all(len(line) <= 42 for line in lines)


def test_shorts_use_narrower_lines():
    ws = words_from("Este e um exemplo de frase mediana para legenda vertical curta")
    for c in segment_words(ws, shorts=True):
        assert all(len(line) <= 32 for line in c.text.split("\n"))


def test_durations_are_clamped_and_never_overlap():
    r = SegmentationRules()
    caps = segment_words(words_from("Ola. Tudo bem. Vamos la. Comecando agora mesmo.", step=0.2), r)
    for a, b in zip(caps, caps[1:], strict=False):
        assert a.end < b.start
    assert all(c.end > c.start and c.end - c.start <= r.max_duration for c in caps)


def test_wrap_prefers_comma():
    assert wrap_two_lines("Primeiro definimos a funcao, depois calculamos o limite dela", 42) \
        == "Primeiro definimos a funcao,\ndepois calculamos o limite dela"


def test_without_word_timestamps_falls_back_to_segments():
    segs = [Segment(start=0, end=2, text="frase sem palavras")]
    assert segment_transcript(segs)[0].text == "frase sem palavras"


# ------------------------------------------------------------------ IA
class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_returning(*responses):
    it = iter(responses)
    return lambda req, timeout=None: FakeResp(json.dumps({"response": next(it)}).encode())


def test_chunk_text_splits_on_sentences():
    parts = ai.chunk_text("Frase um. " * 50, 120)
    assert all(len(p) <= 120 for p in parts) and all(p.endswith(".") for p in parts)


def test_quiz_html_escapes_and_has_four_options():
    q = Quiz.model_validate({"questions": [
        {"question": "O que e <b>2+2</b>?", "correct": "4", "wrong": ["3", "5", "<script>"]}]})
    page = ai.quiz_html(q, "Aula & Teste", seed="x")
    assert "<script>" not in page.split("<script>\nlet")[0]
    assert page.count('<button data-c=') == 4 and "&lt;b&gt;" in page and "Aula &amp; Teste" in page


def test_pick_clips_drops_clips_beyond_video():
    tr = Transcript(language="pt", duration=100, model="f", device="cpu",
                    segments=[Segment(start=0, end=100, text="conteudo")])
    plan = json.dumps({"clips": [{"title": "Bom", "start": 10, "end": 40},
                                 {"title": "Fora", "start": 90, "end": 150}]})
    client = OllamaClient(LLMConfig(), opener=opener_returning(plan))
    clips = ai.pick_clips(client, tr, n=3, max_chars=5000)
    assert [c.title for c in clips] == ["Bom"]


# ------------------------------------------------------------------ apostila
def test_handout_pairs_speech_with_slides_and_escapes(tmp_path):
    (tmp_path / "slides").mkdir()
    s1, s2 = tmp_path / "slides" / "slide_0001.jpg", tmp_path / "slides" / "slide_0002.jpg"
    s1.write_bytes(b"x")
    s2.write_bytes(b"x")
    tr = Transcript(language="pt", duration=20, model="f", device="cpu", segments=[
        Segment(start=1, end=3, text="Introducao <tag>"), Segment(start=11, end=13, text="Segunda parte")])
    page = editorial.build_handout("Aula 1", [SlideFrame(path=s1, timestamp=0), SlideFrame(path=s2, timestamp=10)],
                                   tr, tmp_path / "documentos" / "Apostila.html", "## Objetivo\n- **Aprender**")
    html = page.read_text(encoding="utf-8")
    first, second = html.split('class="bloco"')[1:3]
    assert "Introducao &lt;tag&gt;" in first and "Segunda parte" in second
    assert "../slides/slide_0001.jpg" in html and "<strong>Aprender</strong>" in html


def test_pdf_reports_missing_browser(monkeypatch, tmp_path):
    from luismedia.adapters import pdf
    from luismedia.core.errors import DependencyMissing

    monkeypatch.setattr(pdf.shutil, "which", lambda _: None)
    monkeypatch.setattr(pdf.sys, "platform", "linux")
    monkeypatch.delenv("LUISMEDIA_BROWSER", raising=False)
    with pytest.raises(DependencyMissing):
        pdf.find_browser()
