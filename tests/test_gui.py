"""App desktop rodando sem tela (QT_QPA_PLATFORM=offscreen)."""

from __future__ import annotations

import json
import os
import time

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from .conftest import _has_libass, needs_ffmpeg, needs_libass  # noqa: E402


@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "data"))
    from luismedia.gui.app import MainWindow, make_app

    app = make_app(["teste"])
    w = MainWindow()
    w.show()
    app.processEvents()
    yield app, w
    w.close()


def pump(app, until, timeout=120.0):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if until():
            return True
        time.sleep(0.02)
    return False


def test_presets_fill_options_and_edit_switches_to_custom(window):
    app, w = window
    p = w.process
    p.preset.setCurrentText("Pré-edição (DaVinci / Premiere)")
    opts = p.options()
    assert opts["autocut"]["export_edl"] and not opts["llm"]["enabled"] and not opts["render"]["hardsub"]
    p.o_quiz.setChecked(True)
    assert p.preset.currentText() == "Personalizado" and p.options()["llm"]["quiz"]


def test_options_are_valid_settings(window):
    from luismedia.gui import state

    _, w = window
    s = state.compose(state.load_base_settings(), w.process.options())
    assert s.audio.target_lufs == -14


def test_settings_page_saves(window, tmp_path):
    from luismedia.gui import state

    _, w = window
    w.settings.crf.setValue(23)
    w.settings.save()
    assert state.load_base_settings().render.crf == 23


def test_slides_page_builds_presentation(window, tmp_path):
    from luismedia.stages import presentation

    _, w = window
    md = tmp_path / "a.md"
    md.write_text(w.slides.editor.toPlainText(), encoding="utf-8")
    html = presentation.build_slides(str(md), tmp_path / "a.html").read_text(encoding="utf-8")
    assert html.count('class="slide"') == 3 and "Funções do 1º grau" in html


@needs_ffmpeg
def test_process_page_runs_job_to_the_end(window, tmp_path, lesson_video, monkeypatch):
    import luismedia.pipeline.runner as runner

    from .test_integration import FakeWhisper

    monkeypatch.setattr(runner, "WhisperEngine", lambda cfg: FakeWhisper())
    app, w = window
    p = w.process
    p.preset.setCurrentText("Pré-edição (DaVinci / Premiere)")
    p.add_paths([lesson_video])
    p.out_edit.setText(str(tmp_path / "saida"))
    assert pump(app, lambda: "m" in p.table.item(0, 1).text(), 30)  # duracao lida em segundo plano
    p.btn_start.click()  # pelo botao, como o usuario (o sinal clicked envia um bool)
    assert p.job is not None, "o botao Iniciar nao iniciou o processamento"
    assert pump(app, lambda: p.job is None, 180)
    assert p.table.item(0, 3).text() == "Concluído", p.result.text()
    assert (tmp_path / "saida" / "aula 01" / "aula 01.edl").exists()
    assert lesson_video.exists()


def test_style_page_presets_save_and_preview(window):
    from luismedia.gui import state

    app, w = window
    sp = w.style_page
    sp.tabs.setCurrentIndex(1)
    sp.v.preset.setCurrentText("Neon")
    assert sp.v.style().font == "Archivo Black" and sp.v.style().highlight == "color"
    sp.v.size.setValue(9.5)
    assert sp.v.preset.currentText() == "Personalizado"
    sp.save()
    assert state.load_base_settings().subtitles.style_v.size == 9.5
    if _has_libass():  # a previa e desenhada pelo libass do FFmpeg
        assert pump(app, lambda: sp.v.preview.pixmap() is not None and not sp.v.preview.pixmap().isNull(), 30)


@needs_ffmpeg
@needs_libass
def test_review_flow_in_the_app(window, tmp_path, lesson_video, monkeypatch):
    import luismedia.pipeline.runner as runner

    from .test_subtitles_pro import CountingWhisper

    whisper = CountingWhisper()
    monkeypatch.setattr(runner, "WhisperEngine", lambda cfg: whisper)
    app, w = window
    p = w.process
    p.preset.setCurrentText("Pré-edição (DaVinci / Premiere)")
    p.o_hardsub.setChecked(True)
    p.o_review.setChecked(True)
    p.o_vocab.setText("Whisper, LGPD")
    assert p.options()["whisper"]["vocabulary"] == ["Whisper", "LGPD"]
    p.add_paths([lesson_video])
    p.out_edit.setText(str(tmp_path / "out"))
    p.btn_start.click()
    assert pump(app, lambda: p.job is None, 120)
    assert p.table.item(0, 3).text() == "Revisar legendas" and p.btn_review.isVisibleTo(w)

    p.btn_review.click()  # abre o editor no video certo
    assert pump(app, lambda: w.captions.doc is not None, 10)
    ed = w.captions
    ed.find.setText("wisper")
    ed.repl.setText("Whisper")
    ed.btn_replace.click()
    assert "Whisper" in ed.doc.captions[0].text
    ed.table.selectRow(0)
    ed.text.setPlainText("Olá, turma do Whisper!")
    ed.btn_apply.click()
    ed.keywords.setText("Whisper, turma, Whisper")
    assert ed.keyword_list() == ["Whisper", "turma"]
    ed.btn_approve.click()  # volta para Processar e gera o video legendado
    assert pump(app, lambda: p.job is None and p.table.item(0, 3).text() == "Concluído", 120), p.result.text()
    srt = next((tmp_path / "out").glob("*/legendas/*.srt")).read_text(encoding="utf-8")
    assert "Olá, turma do Whisper!" in srt and whisper.calls == 1
    doc = next((tmp_path / "out").glob("*/legendas/*.captions.json"))
    assert json.loads(doc.read_text(encoding="utf-8"))["keywords"] == ["Whisper", "turma"]


def test_style_page_capcut_controls_templates_and_drag(window, tmp_path):
    app, w = window
    ed = w.style_page.v
    ed.preset.setCurrentText("Marca-texto")
    s = ed.style()
    assert s.highlight == "box" and s.animation == "bounce" and s.emojis
    ed.gradient.setChecked(True)
    assert ed.style().gradient and ed.preset.currentText() == "Personalizado"

    # modelo proprio: salvar, aparece com estrela, exportar, excluir, importar
    ed.save_user_preset("Cliente X")
    assert ed.preset.currentText() == "★ Cliente X" and ed.act_delete.isEnabled()
    assert w.style_page.h.preset.findText("★ Cliente X") < 0  # modelos 9:16 e 16:9 separados
    f = tmp_path / "x.estilo.json"
    ed.export_style(f, "Cliente X")
    ed.delete_user_preset("Cliente X")
    assert ed.preset.findText("★ Cliente X") < 0
    assert ed.import_style(f) == "Cliente X"
    assert ed.preset.currentText() == "★ Cliente X" and ed.style().gradient

    # arrastar na previa muda para posicao livre
    ed.preview.set_image(_pix(270, 480))
    ed.preview.resize(300, 500)
    app.processEvents()
    r = ed.preview.image_rect()
    ed.preview.drag_to(r.left() + r.width() * 0.3, r.top() + r.height() * 0.2, True)
    st = ed.style()
    assert st.position == "custom" and abs(st.pos_x - 30) < 2 and abs(st.pos_y - 20) < 2
    assert ed.pos_x.isEnabled() and not ed.margin.isEnabled()


def _pix(wd, ht):
    from PySide6.QtGui import QColor, QPixmap

    p = QPixmap(wd, ht)
    p.fill(QColor("#334"))
    return p


def test_style_preview_player_with_real_captions(window, tmp_path, lesson_video):
    from luismedia.core.captions import CaptionDoc
    from luismedia.core.models import Segment, Word

    if not _has_libass():
        pytest.skip("ffmpeg sem libass")
    app, w = window
    sp = w.style_page
    sp.tabs.setCurrentIndex(1)
    ed = sp.v
    seg = Segment(start=4.6, end=6.8, text="vamos ganhar dinheiro",
                  words=[Word(start=4.6 + i * 0.6, end=5.0 + i * 0.6, text=t)
                         for i, t in enumerate(["vamos", "ganhar", "dinheiro"])])
    doc = CaptionDoc(video=str(lesson_video), width=320, height=240, captions=[seg], keywords=["dinheiro"])
    sp.set_doc(doc)
    assert pump(app, lambda: ed.source.segments and ed.timeline.isEnabled(), 30)
    assert abs(ed.timeline.maximum() - 12000) < 600  # linha do tempo = duracao do video
    assert ed._moment == pytest.approx(4.6)  # comeca na primeira fala
    assert "Legendas reais" in ed.source_lbl.text()

    ed.play()
    assert ed.playing and ed.btn_play.text() == "❚❚"
    assert pump(app, lambda: len(ed._frames) > 50 and ed._frame_i > 5, 60)
    assert ed.timeline.value() > 4600  # a agulha anda junto com o video
    ed.pause()
    assert not ed.playing and ed.btn_play.text() == "▶"

    ed.timeline.setValue(9000)  # clique em outro ponto da linha do tempo
    assert ed._moment == pytest.approx(9.0)
    assert ed.time_lbl.text().startswith("00:09")

    sp.set_background(None)  # fila vazia: continua com o video revisado
    assert ed.source.video == lesson_video
