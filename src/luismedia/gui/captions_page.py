"""Editor de legendas: revisar o texto do Whisper antes de queimar no video e gerar os cortes."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.captions import CaptionDoc, apply_replacements, realign_words, rebalance
from ..core.models import Segment
from ..core.segmentation import cps
from ..pipeline.runner import captions_edited, find_reviews
from . import state, theme
from .widgets import Card, banner, hint, page_header, row

try:  # o player e opcional: sem QtMultimedia o editor funciona sem video
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget
except Exception:  # noqa: BLE001
    QMediaPlayer = None  # type: ignore[assignment,misc]

COL_START, COL_END, COL_TEXT, COL_CPS = range(4)


def _player_available() -> bool:
    """Sem tela (testes/CI) ou sem backend de audio, o editor funciona sem o player."""
    import os

    from PySide6.QtGui import QGuiApplication

    return (QMediaPlayer is not None and not os.environ.get("LUISMEDIA_NO_PLAYER")
            and QGuiApplication.platformName() not in ("offscreen", "minimal"))


def tc(sec: float) -> str:
    m, s = divmod(max(0.0, sec), 60)
    return f"{int(m):02d}:{s:05.2f}"


class CaptionsPage(QWidget):
    approved = Signal(list)  # caminhos dos videos originais aprovados (para continuar o processamento)
    doc_opened = Signal(object)  # CaptionDoc aberto/salvo (a tela de estilo usa as legendas reais na previa)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")
        self.root: Path | None = None
        self.doc: CaptionDoc | None = None
        self.doc_path: Path | None = None
        self.dirty = False
        self._sel = -1
        self._build()

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 18)
        lay.setSpacing(12)
        lay.addWidget(page_header("Revisar legendas",
                                  "Corrija nomes, termos e pontuação antes de gerar o vídeo legendado e os cortes. "
                                  "As correções valem para SRT, legenda queimada, cortes e apostila."))
        top = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setPlaceholderText("Pasta de saída de um processamento")
        self.btn_folder = QPushButton("Abrir pasta…")
        top.addWidget(QLabel("Lote:"))
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
        left.setMinimumWidth(200)
        split.addWidget(left)

        # ---- player + tabela
        mid = QWidget()
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(10)
        self.player = None
        if _player_available():
            pc = Card()
            self.video = QVideoWidget()
            self.video.setMinimumHeight(220)
            self.player = QMediaPlayer(self)
            self.audio = QAudioOutput(self)
            self.player.setAudioOutput(self.audio)
            self.player.setVideoOutput(self.video)
            self.overlay = QLabel()
            self.overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.overlay.setWordWrap(True)
            self.overlay.setStyleSheet("font-size: 12pt; font-weight: 600; padding: 4px;")
            self.btn_play = QPushButton("▶")
            self.btn_play.setFixedWidth(44)
            self.seek = QSlider(Qt.Orientation.Horizontal)
            self.time = QLabel("00:00.00")
            self.time.setObjectName("muted")
            pc.body.addWidget(self.video, 1)
            pc.body.addWidget(self.overlay)
            pc.body.addWidget(row(self.btn_play, self.seek, self.time, stretch_last=True))
            ml.addWidget(pc, 3)
            self.btn_play.clicked.connect(self._toggle_play)
            self.player.positionChanged.connect(self._on_position)
            self.player.durationChanged.connect(lambda d: self.seek.setRange(0, d))
            self.seek.sliderMoved.connect(self.player.setPosition)

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
        ml.addWidget(self.table, 4)
        split.addWidget(mid)

        # ---- edicao
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(10)
        ed = Card("Legenda selecionada")
        self.text = QPlainTextEdit()
        self.text.setMaximumHeight(90)
        self.start = QDoubleSpinBox()
        self.end = QDoubleSpinBox()
        for sp in (self.start, self.end):
            sp.setRange(0, 86400)
            sp.setDecimals(2)
            sp.setSingleStep(0.1)
            sp.setSuffix(" s")
            sp.setFixedWidth(120)
        self.cps_info = hint("")
        self.btn_apply = QPushButton("Aplicar")
        self.btn_balance = QPushButton("Rebalancear linhas")
        self.btn_merge = QPushButton("Juntar com a próxima")
        self.btn_delete = QPushButton("Excluir")
        ed.body.addWidget(self.text)
        ed.body.addWidget(row(QLabel("Início"), self.start, QLabel("Fim"), self.end))
        ed.body.addWidget(self.cps_info)
        ed.body.addWidget(row(self.btn_apply, self.btn_balance))
        ed.body.addWidget(row(self.btn_merge, self.btn_delete))
        rl.addWidget(ed)

        fr = Card("Localizar e substituir")
        self.find = QLineEdit()
        self.find.setPlaceholderText("Palavra errada (ex.: wisper)")
        self.repl = QLineEdit()
        self.repl.setPlaceholderText("Correção (ex.: Whisper)")
        self.remember = QCheckBox("Lembrar para as próximas aulas")
        self.btn_replace = QPushButton("Substituir em todas")
        fr.body.addWidget(self.find)
        fr.body.addWidget(self.repl)
        fr.body.addWidget(self.remember)
        fr.body.addWidget(self.btn_replace)
        rl.addWidget(fr)

        kw = Card("Palavras-chave em destaque")
        self.keywords = QLineEdit()
        self.keywords.setPlaceholderText("Separadas por vírgula (ex.: Python, função, variável)")
        kw.body.addWidget(self.keywords)
        kw.body.addWidget(hint("Usadas quando o estilo tem \"Destacar palavras-chave\". A IA sugere; você ajusta."))
        rl.addWidget(kw)
        rl.addStretch(1)
        self.btn_save = QPushButton("Salvar")
        self.btn_approve = QPushButton("Aprovar e gerar vídeos")
        self.btn_approve.setObjectName("primary")
        rl.addWidget(self.btn_save)
        rl.addWidget(self.btn_approve)
        right.setMinimumWidth(300)
        right.setMaximumWidth(360)
        split.addWidget(right)
        split.setStretchFactor(1, 1)

        self.btn_folder.clicked.connect(self._pick_folder)
        self.folder.returnPressed.connect(lambda: self.load_root(Path(self.folder.text())))
        self.videos.currentRowChanged.connect(self._open_video)
        self.table.currentCellChanged.connect(lambda r, *_: self._select(r))
        self.btn_apply.clicked.connect(self._apply)
        self.btn_balance.clicked.connect(self._balance)
        self.btn_merge.clicked.connect(self._merge)
        self.btn_delete.clicked.connect(self._delete)
        self.btn_replace.clicked.connect(self._replace_all)
        self.btn_save.clicked.connect(self.save)
        self.keywords.textEdited.connect(lambda _t: self._keywords_edited())
        self.btn_approve.clicked.connect(self._approve)
        self._set_enabled(False)

    def _set_enabled(self, on: bool) -> None:
        for w in (self.btn_apply, self.btn_balance, self.btn_merge, self.btn_delete, self.btn_replace,
                  self.btn_save, self.btn_approve, self.text, self.start, self.end, self.keywords):
            w.setEnabled(on)

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
        self.videos.clear()
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
        self.videos.setCurrentRow(row_)

    def _open_video(self, r: int) -> None:
        if r < 0:
            return
        item = self.videos.item(r)
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        if self.doc_path and path != self.doc_path and not self._confirm_discard():
            return
        self.doc_path, self.doc, self.dirty = path, CaptionDoc.load(path), False
        self.keywords.blockSignals(True)
        self.keywords.setText(", ".join(self.doc.keywords))
        self.keywords.blockSignals(False)
        self.doc_opened.emit(self.doc)
        self._fill_table()
        self._set_enabled(True)
        if self.player is not None and Path(self.doc.video).exists():
            self.player.setSource(QUrl.fromLocalFile(self.doc.video))
        if self.table.rowCount():
            self.table.selectRow(0)

    def _fill_table(self) -> None:
        assert self.doc is not None
        self.table.setRowCount(0)
        for c in self.doc.captions:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self._fill_row(r, c)

    def _fill_row(self, r: int, c: Segment) -> None:
        rate = cps(c)
        items = [tc(c.start), tc(c.end), c.text.replace("\n", " ⏎ "), f"{rate:.0f}"]
        for col, txt in enumerate(items):
            it = QTableWidgetItem(txt)
            if col == COL_CPS and rate > state.load_base_settings().subtitles.max_cps + 0.5:
                it.setForeground(QColor(theme.WARNING))
                it.setToolTip("Rápida demais para ler: encurte o texto ou aumente a duração.")
            self.table.setItem(r, col, it)

    # ------------------------------------------------------------------ edicao
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
        if self.player is not None:
            self.player.setPosition(int(c.start * 1000))

    def _apply(self) -> None:
        if not self.doc or self._sel < 0:
            return
        start, end = self.start.value(), self.end.value()
        if end <= start:
            banner(self.msg, "warn", "O fim precisa ser depois do início.")
            return
        text = "\n".join(line.strip() for line in self.text.toPlainText().strip().splitlines() if line.strip())
        old = self.doc.captions[self._sel].model_copy(update={"start": start, "end": end})
        self.doc.captions[self._sel] = realign_words(old, text) if text != old.text else old
        self._fill_row(self._sel, self.doc.captions[self._sel])
        self.dirty = True
        self._select(self._sel)

    def _balance(self) -> None:
        maxc = state.load_base_settings().subtitles.max_chars_line
        self.text.setPlainText(rebalance(self.text.toPlainText(), maxc))
        self._apply()

    def _merge(self) -> None:
        if not self.doc or not (0 <= self._sel < len(self.doc.captions) - 1):
            return
        a, b = self.doc.captions[self._sel], self.doc.captions[self._sel + 1]
        maxc = state.load_base_settings().subtitles.max_chars_line
        merged = Segment(start=a.start, end=b.end, text=rebalance(f"{a.text} {b.text}", maxc),
                         words=[*a.words, *b.words])
        self.doc.captions[self._sel:self._sel + 2] = [merged]
        self.dirty = True
        self._fill_table()
        self.table.selectRow(self._sel)

    def _delete(self) -> None:
        if not self.doc or self._sel < 0:
            return
        del self.doc.captions[self._sel]
        self.dirty = True
        self._fill_table()
        self.table.selectRow(min(self._sel, self.table.rowCount() - 1))

    def _replace_all(self) -> None:
        wrong, right = self.find.text().strip(), self.repl.text().strip()
        if not self.doc or not wrong:
            return
        n = 0
        for i, c in enumerate(self.doc.captions):
            new = apply_replacements(c.text, {wrong: right})
            if new != c.text:
                self.doc.captions[i] = realign_words(c, new)
                n += 1
        if self.remember.isChecked():
            base = state.load_base_settings()
            reps = {**base.subtitles.replacements, wrong: right}
            state.save_base_settings(state.compose(base, {"subtitles": {"replacements": reps}}))
        self.dirty = self.dirty or n > 0
        self._fill_table()
        extra = " A correção será aplicada nas próximas aulas." if self.remember.isChecked() else ""
        banner(self.msg, "ok", f"{n} legenda(s) corrigida(s).{extra}")

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
        banner(self.msg, "ok", "Legendas salvas.")
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
        banner(self.msg, "ok", "Aprovada. Gerando o vídeo legendado e os cortes na tela Processar…")
        self.approved.emit([src])

    def _source_for(self, doc_path: Path) -> Path | None:
        """Video original: o relatorio do lote guarda o caminho de cada video processado."""
        import json

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

    # ------------------------------------------------------------------ player
    def _toggle_play(self) -> None:
        if self.player is None:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.btn_play.setText("▶")
        else:
            self.player.play()
            self.btn_play.setText("❚❚")

    def _on_position(self, ms: int) -> None:
        t = ms / 1000
        self.time.setText(tc(t))
        if not self.seek.isSliderDown():
            self.seek.setValue(ms)
        cur = next((c for c in (self.doc.captions if self.doc else []) if c.start <= t < c.end), None)
        self.overlay.setText(cur.text.replace("\n", " ") if cur else "")
