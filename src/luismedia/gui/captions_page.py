"""Revisar e editar: texto das legendas, cortes de pausas/vicios e tempos, numa linha do tempo.

Atalhos: Espaco/K tocar-pausar · J/L voltar/avancar 3 s · ←/→ legenda anterior/proxima ·
Delete corta o trecho selecionado · Ctrl+Z desfaz · Ctrl+Y (ou Ctrl+Shift+Z) refaz.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.captions import CaptionDoc, apply_replacements, realign_words, rebalance
from ..core.cleanup import Cut, envelope_from_pcm, read_envelope_wav, removed_seconds
from ..core.models import Segment
from ..core.segmentation import cps
from ..pipeline.runner import captions_edited, find_reviews
from . import state, theme
from .tasks import run_task
from .timeline import Timeline
from .widgets import Card, banner, hint, row

try:  # o player e opcional: sem QtMultimedia o editor funciona sem video
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget
except Exception:  # noqa: BLE001
    QMediaPlayer = None  # type: ignore[assignment,misc]

COL_START, COL_END, COL_TEXT, COL_CPS = range(4)
UNDO_LIMIT = 200


def _player_available() -> bool:
    """Sem tela (testes/CI) ou sem backend de audio, o editor funciona sem o player."""
    import os

    from PySide6.QtGui import QGuiApplication

    return (QMediaPlayer is not None and not os.environ.get("LUISMEDIA_NO_PLAYER")
            and QGuiApplication.platformName() not in ("offscreen", "minimal"))


def tc(sec: float) -> str:
    m, s = divmod(max(0.0, sec), 60)
    return f"{int(m):02d}:{s:05.2f}"


def fmt_span(sec: float) -> str:
    sec = max(0, round(sec))
    return f"{sec // 60}m {sec % 60:02d}s" if sec >= 60 else f"{sec}s"


def load_envelope(doc_path: Path, video: str) -> tuple[list[float], float]:
    """Volume do audio para desenhar a onda: arquivo pronto do pipeline, WAV extraido ou o
    proprio video (FFmpeg)."""
    name = doc_path.name.replace(".captions.json", "")
    audio = doc_path.parent.parent / "audio"
    envp = audio / f"{name}.envelope.json"
    if envp.exists():
        data = json.loads(envp.read_text(encoding="utf-8"))
        return data["rms"], float(data.get("rate", 50))
    wav = audio / f"{name}.wav"
    if wav.exists():
        return read_envelope_wav(wav), 50.0
    import subprocess

    import numpy as np

    from ..adapters import ffmpeg as ff

    res = subprocess.run([ff.find_binary("ffmpeg"), "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "8000",
                          "-f", "s16le", "-"], capture_output=True, timeout=600, **ff.NO_WINDOW)
    return envelope_from_pcm(np.frombuffer(res.stdout, dtype=np.int16), 8000), 50.0


class CaptionsPage(QWidget):
    approved = Signal(list)      # caminhos dos videos originais aprovados (para continuar o processamento)
    doc_opened = Signal(object)  # CaptionDoc aberto/salvo (a tela de estilo usa as legendas reais na previa)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")
        self.root: Path | None = None
        self.doc: CaptionDoc | None = None
        self.doc_path: Path | None = None
        self.dirty = False
        self._sel = -1
        self._undo: list[str] = []
        self._redo: list[str] = []
        self._pending: str | None = None
        self._env_seq = 0
        self._build()

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 18)
        lay.setSpacing(10)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        t = QLabel("Revisar e editar")
        t.setObjectName("pageTitle")
        sub = QLabel("Corrija o texto, ajuste os tempos e escolha quais pausas e vícios saem do vídeo.")
        sub.setObjectName("pageSubtitle")
        titles.addWidget(t)
        titles.addWidget(sub)
        head.addLayout(titles, 1)
        self.btn_undo = QPushButton("↶")
        self.btn_undo.setToolTip("Desfazer (Ctrl+Z)")
        self.btn_redo = QPushButton("↷")
        self.btn_redo.setToolTip("Refazer (Ctrl+Y)")
        for b in (self.btn_undo, self.btn_redo):
            b.setObjectName("iconBtn")
            b.setFixedSize(36, 34)
        self.btn_save = QPushButton("Salvar")
        self.btn_approve = QPushButton("Aprovar e gerar vídeos")
        self.btn_approve.setObjectName("primary")
        for w in (self.btn_undo, self.btn_redo):
            head.addWidget(w)
        head.addSpacing(8)
        head.addWidget(self.btn_save)
        head.addWidget(self.btn_approve)
        lay.addLayout(head)

        top = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setPlaceholderText("Pasta de saída de um processamento")
        self.btn_folder = QPushButton("Abrir pasta…")
        top.addWidget(QLabel("Lote"))
        top.addWidget(self.folder, 1)
        top.addWidget(self.btn_folder)
        lay.addLayout(top)
        self.msg = QLabel()
        self.msg.setObjectName("banner")
        self.msg.setWordWrap(True)
        self.msg.setVisible(False)
        lay.addWidget(self.msg)

        split = QSplitter(Qt.Orientation.Horizontal)
        lay.addWidget(split, 1)

        # ---- lista de videos
        left = Card("Vídeos")
        self.videos = QListWidget()
        self.videos.setObjectName("nav")
        left.body.addWidget(self.videos, 1)
        left.setMinimumWidth(190)
        left.setMaximumWidth(250)
        split.addWidget(left)

        # ---- player + linha do tempo + tabela
        mid = QWidget()
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(8)
        self.player = None
        self.btn_play = QPushButton("▶")
        self.btn_play.setObjectName("play")
        self.btn_play.setFixedSize(38, 38)
        self.btn_play.setToolTip("Tocar / pausar (Espaço)")
        self.time = QLabel("00:00.00")
        self.time.setObjectName("timecode")
        self.preview_cuts = QCheckBox("Pular cortes")
        self.preview_cuts.setChecked(True)
        self.preview_cuts.setToolTip("Ao tocar, pula os trechos marcados para corte")
        self.overlay = QLabel()
        self.overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay.setWordWrap(True)
        self.overlay.setStyleSheet("font-size: 12pt; font-weight: 600; padding: 4px;")
        if _player_available():
            pc = Card()
            self.video = QVideoWidget()
            self.video.setMinimumHeight(200)
            self.player = QMediaPlayer(self)
            self.audio = QAudioOutput(self)
            self.player.setAudioOutput(self.audio)
            self.player.setVideoOutput(self.video)
            pc.body.addWidget(self.video, 1)
            pc.body.addWidget(self.overlay)
            ml.addWidget(pc, 3)
            self.player.positionChanged.connect(self._on_position)
            self.player.playbackStateChanged.connect(lambda *_: self._sync_play_button())
        else:
            ml.addWidget(self.overlay)

        tl = Card()
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.btn_zoom_out = QPushButton("−")
        self.btn_zoom_in = QPushButton("+")
        self.btn_fit = QPushButton("Tudo")
        for b in (self.btn_zoom_out, self.btn_zoom_in):
            b.setObjectName("iconBtn")
            b.setFixedSize(30, 28)
        self.btn_fit.setToolTip("Ver o vídeo inteiro")
        self.btn_zoom_in.setToolTip("Aproximar (Ctrl+rolar)")
        self.btn_zoom_out.setToolTip("Afastar (Ctrl+rolar)")
        self.btn_cut_sel = QPushButton("✂ Cortar")
        self.btn_cut_sel.setToolTip("Arraste na onda para selecionar um trecho e corte (Delete)")
        self.btn_cut_sel.setEnabled(False)
        self.cut_summary = QLabel()
        self.cut_summary.setObjectName("muted")
        bar.addWidget(self.btn_play)
        bar.addWidget(self.time)
        bar.addSpacing(10)
        bar.addWidget(self.preview_cuts)
        bar.addStretch(1)
        bar.addWidget(self.cut_summary)
        bar.addSpacing(10)
        bar.addWidget(self.btn_cut_sel)
        bar.addWidget(self.btn_zoom_out)
        bar.addWidget(self.btn_zoom_in)
        bar.addWidget(self.btn_fit)
        tl.body.addLayout(bar)
        self.timeline = Timeline()
        tl.body.addWidget(self.timeline)
        ml.addWidget(tl)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Início", "Fim", "Texto", "Car./s"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        hh = self.table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        hh.setSectionResizeMode(COL_TEXT, QHeaderView.ResizeMode.Stretch)
        for c, w in ((COL_START, 80), (COL_END, 80), (COL_CPS, 64)):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(c, w)
        ml.addWidget(self.table, 2)
        split.addWidget(mid)

        # ---- painel da direita (abas)
        self.side = QTabWidget()
        self.side.setMinimumWidth(290)
        self.side.setMaximumWidth(360)
        self.side.addTab(self._tab_caption(), "Legenda")
        self.side.addTab(self._tab_cuts(), "Cortes")
        self.side.addTab(self._tab_text(), "Texto")
        split.addWidget(self.side)
        split.setStretchFactor(1, 1)

        self.btn_folder.clicked.connect(lambda _c=False: self._pick_folder())
        self.folder.returnPressed.connect(lambda: self.load_root(Path(self.folder.text())))
        self.videos.currentRowChanged.connect(self._open_video)
        self.table.currentCellChanged.connect(lambda r, *_: self._select(r))
        self.btn_apply.clicked.connect(lambda _c=False: self._apply())
        self.btn_balance.clicked.connect(lambda _c=False: self._balance())
        self.btn_merge.clicked.connect(lambda _c=False: self._merge())
        self.btn_delete.clicked.connect(lambda _c=False: self._delete())
        self.btn_replace.clicked.connect(lambda _c=False: self._replace_all())
        self.btn_save.clicked.connect(lambda _c=False: self.save())
        self.btn_approve.clicked.connect(lambda _c=False: self._approve())
        self.btn_undo.clicked.connect(lambda _c=False: self.undo())
        self.btn_redo.clicked.connect(lambda _c=False: self.redo())
        self.keywords.textEdited.connect(lambda _t: self._keywords_edited())
        self.btn_play.clicked.connect(lambda _c=False: self.toggle_play())
        self.btn_zoom_in.clicked.connect(lambda _c=False: self.timeline.zoom(1.5))
        self.btn_zoom_out.clicked.connect(lambda _c=False: self.timeline.zoom(1 / 1.5))
        self.btn_fit.clicked.connect(lambda _c=False: self.timeline.zoom_to(0, self.timeline.duration))
        self.btn_cut_sel.clicked.connect(lambda _c=False: self.cut_selection())
        self.cuts_list.itemChanged.connect(self._cut_item_changed)
        self.cuts_list.currentRowChanged.connect(self._cut_item_selected)
        self.btn_all_on.clicked.connect(lambda _c=False: self._set_all_cuts(True))
        self.btn_all_off.clicked.connect(lambda _c=False: self._set_all_cuts(False))
        self.btn_cut_remove.clicked.connect(lambda _c=False: self._remove_cut())
        self.timeline.seek_requested.connect(self.seek)
        self.timeline.caption_selected.connect(lambda i: self.table.selectRow(i))
        self.timeline.caption_edit_started.connect(lambda _i: self._begin_pending())
        self.timeline.caption_edited.connect(self._timeline_caption_edited)
        self.timeline.cut_toggled.connect(self.toggle_cut)
        self.timeline.selection_changed.connect(lambda a, b: self.btn_cut_sel.setEnabled(b > a))

        for seq, fn in ((QKeySequence.StandardKey.Undo, self.undo), (QKeySequence.StandardKey.Redo, self.redo),
                        (QKeySequence("Ctrl+Y"), self.redo), (QKeySequence.StandardKey.Save, self.save)):
            act = QAction(self)
            act.setShortcut(seq)
            act.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            act.triggered.connect(lambda _c=False, fn=fn: fn())
            self.addAction(act)
        self._set_enabled(False)

    def _tab_caption(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 10, 4, 4)
        lay.setSpacing(10)
        self.text = QPlainTextEdit()
        self.text.setMaximumHeight(96)
        self.start = QDoubleSpinBox()
        self.end = QDoubleSpinBox()
        for sp in (self.start, self.end):
            sp.setRange(0, 86400)
            sp.setDecimals(2)
            sp.setSingleStep(0.1)
            sp.setSuffix(" s")
            sp.setFixedWidth(110)
        self.cps_info = hint("")
        self.btn_apply = QPushButton("Aplicar")
        self.btn_apply.setObjectName("primary")
        self.btn_balance = QPushButton("Rebalancear linhas")
        self.btn_merge = QPushButton("Juntar com a próxima")
        self.btn_delete = QPushButton("Excluir legenda")
        lay.addWidget(self.text)
        lay.addWidget(row(QLabel("Início"), self.start, QLabel("Fim"), self.end))
        lay.addWidget(self.cps_info)
        lay.addWidget(row(self.btn_apply, self.btn_balance))
        lay.addWidget(row(self.btn_merge, self.btn_delete))
        lay.addWidget(hint("Dica: arraste os blocos na linha do tempo para ajustar os tempos; "
                           "puxe as bordas para encurtar ou alongar."))
        lay.addStretch(1)
        return w

    def _tab_cuts(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 10, 4, 4)
        lay.setSpacing(8)
        self.cuts_info = QLabel()
        self.cuts_info.setWordWrap(True)
        self.cuts_info.setObjectName("cardTitle")
        self.cuts_list = QListWidget()
        self.cuts_list.setObjectName("cutsList")
        self.btn_all_on = QPushButton("Marcar todos")
        self.btn_all_off = QPushButton("Desmarcar todos")
        self.btn_cut_remove = QPushButton("Remover corte manual")
        self.btn_cut_remove.setEnabled(False)
        lay.addWidget(self.cuts_info)
        lay.addWidget(row(self.btn_all_on, self.btn_all_off))
        lay.addWidget(self.cuts_list, 1)
        lay.addWidget(self.btn_cut_remove)
        lay.addWidget(hint("Marcado = sai do vídeo. Pausas com som de fundo e vícios duvidosos "
                           "(“né”, “tipo”) vêm desmarcados para você decidir."))
        return w

    def _tab_text(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 10, 4, 4)
        lay.setSpacing(8)
        cap = QLabel("Localizar e substituir")
        cap.setObjectName("cardTitle")
        self.find = QLineEdit()
        self.find.setPlaceholderText("Palavra errada (ex.: wisper)")
        self.repl = QLineEdit()
        self.repl.setPlaceholderText("Correção (ex.: Whisper)")
        self.remember = QCheckBox("Lembrar para as próximas aulas")
        self.btn_replace = QPushButton("Substituir em todas")
        cap2 = QLabel("Palavras-chave em destaque")
        cap2.setObjectName("cardTitle")
        self.keywords = QLineEdit()
        self.keywords.setPlaceholderText("Separadas por vírgula (ex.: Python, função, variável)")
        for x in (cap, self.find, self.repl, self.remember, self.btn_replace):
            lay.addWidget(x)
        lay.addSpacing(14)
        lay.addWidget(cap2)
        lay.addWidget(self.keywords)
        lay.addWidget(hint("Usadas quando o estilo tem \"Destacar palavras-chave\". A IA sugere; você ajusta."))
        lay.addStretch(1)
        return w

    def _set_enabled(self, on: bool) -> None:
        for w in (self.btn_apply, self.btn_balance, self.btn_merge, self.btn_delete, self.btn_replace,
                  self.btn_save, self.btn_approve, self.text, self.start, self.end, self.keywords,
                  self.btn_all_on, self.btn_all_off, self.btn_play, self.timeline):
            w.setEnabled(on)
        self._sync_undo()

    # ------------------------------------------------------------------ carregar
    def _pick_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Pasta de saída do processamento", self.folder.text())
        if d:
            self.load_root(Path(d))

    def load_root(self, root: Path, select: str | None = None) -> None:
        if not self._confirm_discard():
            return
        self.root = root
        self.folder.setText(str(root))
        self.videos.blockSignals(True)
        self.videos.clear()
        self.videos.blockSignals(False)
        docs = find_reviews(root)
        for p in docs:
            try:
                d = CaptionDoc.load(p)
            except Exception:  # noqa: BLE001
                continue
            item = QListWidgetItem(("✔ " if d.approved else "● ") + p.name.replace(".captions.json", ""))
            item.setData(Qt.ItemDataRole.UserRole, str(p))
            item.setForeground(QColor(theme.SUCCESS if d.approved else theme.WARNING))
            item.setToolTip("Aprovada" if d.approved else "Aguardando revisão")
            self.videos.addItem(item)
        if not docs:
            banner(self.msg, "warn", "Nenhuma legenda encontrada nessa pasta. Processe os vídeos primeiro.")
            self._set_enabled(False)
            return
        pending = sum(1 for i in range(self.videos.count()) if self.videos.item(i).text().startswith("●"))
        banner(self.msg, "info" if pending else "ok",
               f"{pending} vídeo(s) aguardando revisão." if pending else "Todas as legendas deste lote estão aprovadas.")
        row_ = next((i for i in range(self.videos.count())
                     if select and select in self.videos.item(i).text()), 0)
        self.doc_path = None
        self.videos.setCurrentRow(row_)
        if self.doc_path is None:  # mesma linha de antes: forca abrir
            self._open_video(row_)

    def _open_video(self, r: int) -> None:
        if r < 0:
            return
        item = self.videos.item(r)
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        if self.doc_path and path != self.doc_path and not self._confirm_discard():
            return
        self.doc_path, self.doc, self.dirty = path, CaptionDoc.load(path), False
        self._undo.clear()
        self._redo.clear()
        self.keywords.blockSignals(True)
        self.keywords.setText(", ".join(self.doc.keywords))
        self.keywords.blockSignals(False)
        self.doc_opened.emit(self.doc)
        self.timeline.reset_view()
        self.timeline.set_envelope([])
        self._refresh_all()
        self._set_enabled(True)
        if self.player is not None and Path(self.doc.video).exists():
            self.player.setSource(QUrl.fromLocalFile(self.doc.video))
        if self.table.rowCount():
            self.table.selectRow(0)
        self._env_seq += 1
        seq, video = self._env_seq, self.doc.video
        run_task(lambda _p: load_envelope(path, video),
                 on_done=lambda res, seq=seq: self._env_ready(res, seq),
                 on_error=lambda _e: None)

    def _env_ready(self, res: tuple[list[float], float], seq: int) -> None:
        if seq == self._env_seq:
            self.timeline.set_envelope(*res)

    def _duration(self) -> float:
        if not self.doc:
            return 0.0
        d = self.doc.duration or 0.0
        if self.player is not None and self.player.duration() > 0:
            d = max(d, self.player.duration() / 1000)
        return max(d, max((c.end for c in self.doc.captions), default=0.0) + 0.5)

    # ------------------------------------------------------------------ vistas
    def _refresh_all(self) -> None:
        self._fill_table()
        self._fill_cuts()
        self._refresh_timeline()

    def _refresh_timeline(self) -> None:
        if self.doc:
            self.timeline.set_data(self._duration(), self.doc.captions, self.doc.cuts)
            self.timeline.set_selected(self._sel)
        self._update_cut_summary()

    def _fill_table(self) -> None:
        assert self.doc is not None
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for c in self.doc.captions:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self._fill_row(r, c)
        self.table.blockSignals(False)

    def _fill_row(self, r: int, c: Segment) -> None:
        rate = cps(c)
        items = [tc(c.start), tc(c.end), c.text.replace("\n", " ⏎ "), f"{rate:.0f}"]
        for col, txt in enumerate(items):
            it = QTableWidgetItem(txt)
            if col == COL_CPS and rate > state.load_base_settings().subtitles.max_cps + 0.5:
                it.setForeground(QColor(theme.WARNING))
                it.setToolTip("Rápida demais para ler: encurte o texto ou aumente a duração.")
            self.table.setItem(r, col, it)

    def _fill_cuts(self) -> None:
        self.cuts_list.blockSignals(True)
        self.cuts_list.clear()
        for c in (self.doc.cuts if self.doc else []):
            it = QListWidgetItem(f"{tc(c.start)}  ·  {c.label or c.kind}  ·  {c.duration:.1f} s")
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if c.enabled else Qt.CheckState.Unchecked)
            it.setToolTip("Marcado: este trecho sai do vídeo")
            self.cuts_list.addItem(it)
        self.cuts_list.blockSignals(False)
        self._update_cut_summary()

    def _update_cut_summary(self) -> None:
        if not self.doc:
            self.cut_summary.setText("")
            self.cuts_info.setText("")
            return
        on = [c for c in self.doc.cuts if c.enabled]
        dur = self._duration()
        removed = removed_seconds(self.doc.cuts, dur)
        if not self.doc.cuts:
            self.cuts_info.setText("Nenhuma pausa ou vício encontrado. Arraste na onda para cortar um trecho.")
            self.cut_summary.setText("")
            return
        self.cuts_info.setText(f"{len(on)} de {len(self.doc.cuts)} cortes marcados · tira {fmt_span(removed)}\n"
                               f"Vídeo final: {fmt_span(dur - removed)} (antes {fmt_span(dur)})")
        self.cut_summary.setText(f"✂ {len(on)} cortes · −{fmt_span(removed)}")

    # ------------------------------------------------------------------ desfazer / refazer
    def _snapshot(self) -> str:
        assert self.doc is not None
        return json.dumps({"captions": [c.model_dump() for c in self.doc.captions],
                           "cuts": [c.model_dump() for c in self.doc.cuts],
                           "keywords": self.doc.keywords})

    def _checkpoint(self) -> None:
        if not self.doc:
            return
        self._undo.append(self._snapshot())
        del self._undo[:-UNDO_LIMIT]
        self._redo.clear()
        self.dirty = True
        self._sync_undo()

    def _begin_pending(self) -> None:
        self._pending = self._snapshot() if self.doc else None

    def _restore_snapshot(self, raw: str) -> None:
        assert self.doc is not None
        data = json.loads(raw)
        self.doc.captions = [Segment.model_validate(c) for c in data["captions"]]
        self.doc.cuts = [Cut.model_validate(c) for c in data["cuts"]]
        self.doc.keywords = data["keywords"]
        self.keywords.setText(", ".join(self.doc.keywords))
        self.dirty = True
        sel = min(self._sel, len(self.doc.captions) - 1)
        self._refresh_all()
        if sel >= 0:
            self.table.selectRow(sel)
        self._sync_undo()

    def undo(self) -> None:
        if not self.doc or not self._undo:
            return
        self._redo.append(self._snapshot())
        self._restore_snapshot(self._undo.pop())
        banner(self.msg, "info", "Desfeito.")

    def redo(self) -> None:
        if not self.doc or not self._redo:
            return
        self._undo.append(self._snapshot())
        self._restore_snapshot(self._redo.pop())
        banner(self.msg, "info", "Refeito.")

    def _sync_undo(self) -> None:
        on = self.doc is not None
        self.btn_undo.setEnabled(on and bool(self._undo))
        self.btn_redo.setEnabled(on and bool(self._redo))

    # ------------------------------------------------------------------ edicao do texto
    def _select(self, r: int) -> None:
        if not self.doc or not (0 <= r < len(self.doc.captions)):
            return
        self._sel = r
        c = self.doc.captions[r]
        self.text.setPlainText(c.text)
        self.start.setValue(c.start)
        self.end.setValue(c.end)
        self.cps_info.setText(f"{len(c.text.replace(chr(10), ' '))} caracteres · {cps(c):.1f} car./s "
                              f"(máx. recomendado: {state.load_base_settings().subtitles.max_cps:.0f})")
        self.timeline.set_selected(r)
        self.seek(c.start)

    def _apply(self) -> None:
        if not self.doc or self._sel < 0:
            return
        start, end = self.start.value(), self.end.value()
        if end <= start:
            banner(self.msg, "warn", "O fim precisa ser depois do início.")
            return
        text = "\n".join(line.strip() for line in self.text.toPlainText().strip().splitlines() if line.strip())
        cur = self.doc.captions[self._sel]
        if text == cur.text and start == cur.start and end == cur.end:
            return
        self._checkpoint()
        old = cur.model_copy(update={"start": start, "end": end})
        self.doc.captions[self._sel] = realign_words(old, text) if text != old.text else old
        self._fill_row(self._sel, self.doc.captions[self._sel])
        self._refresh_timeline()
        self._select(self._sel)

    def _balance(self) -> None:
        maxc = state.load_base_settings().subtitles.max_chars_line
        self.text.setPlainText(rebalance(self.text.toPlainText(), maxc))
        self._apply()

    def _merge(self) -> None:
        if not self.doc or not (0 <= self._sel < len(self.doc.captions) - 1):
            return
        self._checkpoint()
        a, b = self.doc.captions[self._sel], self.doc.captions[self._sel + 1]
        maxc = state.load_base_settings().subtitles.max_chars_line
        merged = Segment(start=a.start, end=b.end, text=rebalance(f"{a.text} {b.text}", maxc),
                         words=[*a.words, *b.words])
        self.doc.captions[self._sel:self._sel + 2] = [merged]
        self._fill_table()
        self._refresh_timeline()
        self.table.selectRow(self._sel)

    def _delete(self) -> None:
        if not self.doc or self._sel < 0:
            return
        self._checkpoint()
        del self.doc.captions[self._sel]
        self._fill_table()
        self._refresh_timeline()
        self.table.selectRow(min(self._sel, self.table.rowCount() - 1))

    def _replace_all(self) -> None:
        wrong, right = self.find.text().strip(), self.repl.text().strip()
        if not self.doc or not wrong:
            return
        before = self._snapshot()
        n = 0
        for i, c in enumerate(self.doc.captions):
            new = apply_replacements(c.text, {wrong: right})
            if new != c.text:
                self.doc.captions[i] = realign_words(c, new)
                n += 1
        if n:
            self._undo.append(before)
            self._redo.clear()
            self.dirty = True
            self._sync_undo()
        if self.remember.isChecked():
            base = state.load_base_settings()
            reps = {**base.subtitles.replacements, wrong: right}
            state.save_base_settings(state.compose(base, {"subtitles": {"replacements": reps}}))
        self._fill_table()
        self._refresh_timeline()
        extra = " A correção será aplicada nas próximas aulas." if self.remember.isChecked() else ""
        banner(self.msg, "ok", f"{n} legenda(s) corrigida(s).{extra}")

    def _timeline_caption_edited(self, i: int, start: float, end: float, done: bool) -> None:
        if not self.doc or not (0 <= i < len(self.doc.captions)):
            return
        c = self.doc.captions[i]
        shift = start - c.start if abs((end - start) - (c.end - c.start)) < 1e-6 else 0.0
        words = c.words
        if shift:  # bloco movido: as palavras andam junto
            words = [w.model_copy(update={"start": w.start + shift, "end": w.end + shift}) for w in c.words]
        self.doc.captions[i] = c.model_copy(update={"start": start, "end": end, "words": words})
        if done:
            if self._pending is not None and self._pending != self._snapshot():
                self._undo.append(self._pending)
                del self._undo[:-UNDO_LIMIT]
                self._redo.clear()
                self.dirty = True
                self._sync_undo()
            self._pending = None
            self._fill_row(i, self.doc.captions[i])
            if i == self._sel:
                self.start.setValue(start)
                self.end.setValue(end)

    # ------------------------------------------------------------------ cortes
    def toggle_cut(self, k: int) -> None:
        if not self.doc or not (0 <= k < len(self.doc.cuts)):
            return
        self._checkpoint()
        c = self.doc.cuts[k]
        self.doc.cuts[k] = c.model_copy(update={"enabled": not c.enabled})
        self._fill_cuts()
        self._refresh_timeline()

    def _cut_item_changed(self, item: QListWidgetItem) -> None:
        if not self.doc:
            return
        k = self.cuts_list.row(item)
        on = item.checkState() == Qt.CheckState.Checked
        if 0 <= k < len(self.doc.cuts) and self.doc.cuts[k].enabled != on:
            self._checkpoint()
            self.doc.cuts[k] = self.doc.cuts[k].model_copy(update={"enabled": on})
            self._refresh_timeline()

    def _cut_item_selected(self, k: int) -> None:
        if not self.doc or not (0 <= k < len(self.doc.cuts)):
            self.btn_cut_remove.setEnabled(False)
            return
        c = self.doc.cuts[k]
        self.btn_cut_remove.setEnabled(c.kind == "manual")
        self.seek(max(0.0, c.start - 1.0))
        self.timeline.set_selected(-1)

    def _set_all_cuts(self, on: bool) -> None:
        if not self.doc or all(c.enabled == on for c in self.doc.cuts):
            return
        self._checkpoint()
        self.doc.cuts = [c.model_copy(update={"enabled": on}) for c in self.doc.cuts]
        self._fill_cuts()
        self._refresh_timeline()

    def cut_selection(self) -> None:
        if not self.doc or not self.timeline.selection:
            return
        a, b = self.timeline.selection
        if b - a < 0.05:
            return
        self._checkpoint()
        self.doc.cuts = sorted([*self.doc.cuts, Cut(start=a, end=b, kind="manual", label="Corte manual")],
                               key=lambda c: (c.start, c.end))
        self.timeline.clear_selection()
        self._fill_cuts()
        self._refresh_timeline()
        banner(self.msg, "ok", f"Trecho de {b - a:.1f} s marcado para corte. Ctrl+Z desfaz.")

    def _remove_cut(self) -> None:
        k = self.cuts_list.currentRow()
        if not self.doc or not (0 <= k < len(self.doc.cuts)) or self.doc.cuts[k].kind != "manual":
            return
        self._checkpoint()
        del self.doc.cuts[k]
        self._fill_cuts()
        self._refresh_timeline()

    # ------------------------------------------------------------------ salvar
    def keyword_list(self) -> list[str]:
        seen: dict[str, None] = {}
        for k in self.keywords.text().split(","):
            if k.strip():
                seen.setdefault(k.strip(), None)
        return list(seen)[:30]

    def _keywords_edited(self) -> None:
        self.dirty = True

    def save(self) -> bool:
        if not self.doc or not self.doc_path:
            return False
        self.doc.keywords = self.keyword_list()
        self.doc.save(self.doc_path)
        self.doc_opened.emit(self.doc)
        captions_edited(self.doc_path.parent.parent)
        self.dirty = False
        banner(self.msg, "ok", "Alterações salvas.")
        return True

    def _approve(self) -> None:
        if not self.doc or not self.doc_path:
            return
        self.doc.approved = True
        self.save()
        item = self.videos.currentItem()
        item.setText("✔ " + item.text()[2:])
        item.setForeground(QColor(theme.SUCCESS))
        src = self._source_for(self.doc_path)
        if src is None:
            banner(self.msg, "warn", "Aprovada, mas não achei o vídeo original deste lote para continuar. "
                                     "Adicione-o na tela Processar e clique em Iniciar.")
            return
        banner(self.msg, "ok", "Aprovada. Gerando o vídeo final…")
        self.approved.emit([src])

    def _source_for(self, doc_path: Path) -> Path | None:
        """Video original: o relatorio do lote guarda o caminho de cada video processado."""
        rel = doc_path.parent.parent.parent / "relatorio.json"
        name = doc_path.parent.parent.name
        try:
            for r in json.loads(rel.read_text(encoding="utf-8")):
                if Path(r["source"]).stem == name and Path(r["source"]).exists():
                    return Path(r["source"])
        except (OSError, ValueError, KeyError):
            pass
        return None

    def _confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        ans = QMessageBox.question(self, "Alterações não salvas", "Salvar as alterações nesta legenda?",
                                   QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                                   | QMessageBox.StandardButton.Cancel)
        if ans == QMessageBox.StandardButton.Cancel:
            return False
        if ans == QMessageBox.StandardButton.Save:
            self.save()
        self.dirty = False
        return True

    # ------------------------------------------------------------------ player e atalhos
    def seek(self, t: float) -> None:
        t = max(0.0, t)
        if self.player is not None:
            self.player.setPosition(int(t * 1000))
        else:
            self._show_time(t)
        self.timeline.set_playhead(t)

    def _playing(self) -> bool:
        return self.player is not None and \
            self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def toggle_play(self) -> None:
        if self.player is None:
            return
        if self._playing():
            self.player.pause()
        else:
            self.player.play()
        self._sync_play_button()

    def _sync_play_button(self) -> None:
        self.btn_play.setText("❚❚" if self._playing() else "▶")

    def _show_time(self, t: float) -> None:
        self.time.setText(tc(t))
        cur = next((c for c in (self.doc.captions if self.doc else []) if c.start <= t < c.end), None)
        self.overlay.setText(cur.text.replace("\n", " ") if cur else "")

    def _on_position(self, ms: int) -> None:
        t = ms / 1000
        if self._playing() and self.preview_cuts.isChecked() and self.doc:
            for c in self.doc.cuts:
                if c.enabled and c.start <= t < c.end - 0.03:
                    self.player.setPosition(int(c.end * 1000) + 1)
                    return
        self._show_time(t)
        self.timeline.set_playhead(t, follow=self._playing())

    def keyPressEvent(self, e) -> None:  # noqa: N802
        fw = self.focusWidget()
        typing = isinstance(fw, (QPlainTextEdit, QLineEdit, QAbstractSpinBox))
        if typing or not self.doc or e.modifiers() & (Qt.KeyboardModifier.ControlModifier
                                                      | Qt.KeyboardModifier.AltModifier):
            super().keyPressEvent(e)
            return
        k = e.key()
        now = self.timeline.playhead
        if k in (Qt.Key.Key_Space, Qt.Key.Key_K):
            self.toggle_play()
        elif k == Qt.Key.Key_J:
            self.seek(now - 3)
        elif k == Qt.Key.Key_L:
            self.seek(now + 3)
        elif k in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.timeline.selection:
            self.cut_selection()
        elif k == Qt.Key.Key_Left and self.doc.captions:
            self.table.selectRow(max(0, self._sel - 1))
        elif k == Qt.Key.Key_Right and self.doc.captions:
            self.table.selectRow(min(len(self.doc.captions) - 1, self._sel + 1))
        else:
            super().keyPressEvent(e)
            return
        e.accept()
