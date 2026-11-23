"""Pagina principal: fila de videos, preset, opcoes e acompanhamento do processamento."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from PySide6.QtCore import QStandardPaths, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..adapters import ffmpeg as ff
from ..cli import VIDEO_EXT
from ..diagnostics import builtin_profiles
from . import state, theme
from .tasks import PipelineJob, run_task, start_job
from .widgets import Card, banner, hint, page_header, row, toggle

STAGE_ORDER = ["validacao", "autocut", "audio", "transcricao", "limpeza", "masterizacao", "ia", "resumo", "quiz",
               "palavras-chave", "edicao", "legendas", "hardsub", "cortes", "slides", "apostila"]
STAGE_NAMES = {
    "validacao": "Validando", "autocut": "Cortando pausas", "audio": "Extraindo áudio",
    "limpeza": "Achando pausas e vícios", "edicao": "Aplicando os cortes", "legendas": "Gerando legendas",
    "palavras-chave": "Escolhendo palavras-chave", "revisao": "Aguardando revisão",
    "transcricao": "Transcrevendo", "masterizacao": "Masterizando voz", "hardsub": "Queimando legenda",
    "ia": "IA local", "resumo": "Gerando resumo", "quiz": "Gerando quiz", "cortes": "Gerando cortes 9:16",
    "slides": "Detectando slides", "apostila": "Montando apostila",
}
ENCODERS = [("Automático (testa a placa)", "auto"), ("GPU NVIDIA (NVENC)", "h264_nvenc"),
            ("GPU AMD (AMF)", "h264_amf"), ("GPU Intel (QSV)", "h264_qsv"), ("CPU (x264)", "libx264")]
COL_NAME, COL_DUR, COL_STAGE, COL_STATUS = range(4)


def fmt_duration(sec: float) -> str:
    s = int(round(sec))
    return f"{s // 3600}h {s % 3600 // 60:02d}m" if s >= 3600 else f"{s // 60}m {s % 60:02d}s"


class DropFrame(QFrame):
    """Area que aceita arquivos e pastas arrastados do Explorer."""

    dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)

    def _set_active(self, on: bool) -> None:
        self.setProperty("active", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, e) -> None:  # noqa: N802 - API do Qt
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._set_active(True)

    def dragLeaveEvent(self, e) -> None:  # noqa: N802
        self._set_active(False)

    def dropEvent(self, e) -> None:  # noqa: N802
        self._set_active(False)
        self.dropped.emit([Path(u.toLocalFile()) for u in e.mimeData().urls() if u.isLocalFile()])


class ProcessPage(QWidget):
    busy_changed = Signal(bool)
    queue_changed = Signal(object)        # primeiro video da fila (para a previa de estilo)
    review_requested = Signal(str, str)   # pasta do lote, nome do video
    job_started = Signal(object)          # PipelineJob (a tela Inicio acompanha o progresso)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")
        self.job: PipelineJob | None = None
        self.paths: list[Path] = []
        self._overrides: dict[Path, dict] = {}  # escolhas da tela Inicio por video
        self._loading = False
        self._build()
        self._restore()

    # ------------------------------------------------------------------ layout
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 18)
        root.setSpacing(14)
        root.addWidget(page_header("Processar aulas",
                                   "Arraste os vídeos, escolha um modo e clique em Iniciar. "
                                   "Os arquivos originais nunca são alterados."))

        body = QHBoxLayout()
        body.setSpacing(16)
        root.addLayout(body, 1)

        # ---- coluna esquerda: fila + saida + progresso
        left = QVBoxLayout()
        left.setSpacing(12)
        body.addLayout(left, 3)

        self.drop = DropFrame()
        dl = QVBoxLayout(self.drop)
        dl.setContentsMargins(14, 12, 14, 12)
        dl.setSpacing(8)
        head = QHBoxLayout()
        self.lbl_queue = QLabel("Fila de vídeos")
        self.lbl_queue.setObjectName("cardTitle")
        head.addWidget(self.lbl_queue)
        head.addStretch(1)
        self.btn_add = QPushButton("Adicionar vídeos…")
        self.btn_add_dir = QPushButton("Adicionar pasta…")
        self.btn_remove = QPushButton("Remover")
        self.btn_clear = QPushButton("Limpar")
        for b in (self.btn_add, self.btn_add_dir, self.btn_remove, self.btn_clear):
            head.addWidget(b)
        dl.addLayout(head)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Vídeo", "Duração", "Etapa", "Status"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        hh = self.table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        hh.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        for c, w in ((COL_DUR, 90), (COL_STAGE, 170), (COL_STATUS, 140)):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(c, w)
        dl.addWidget(self.table, 1)
        self.empty_hint = hint("Arraste vídeos ou pastas para cá (MP4, MKV, MOV, WEBM).")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dl.addWidget(self.empty_hint)
        left.addWidget(self.drop, 1)

        out_card = Card("Pasta de saída")
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("Onde salvar os resultados")
        self.btn_out = QPushButton("Escolher…")
        out_card.body.addWidget(row(self.out_edit, self.btn_out, stretch_last=True))
        left.addWidget(out_card)

        prog_card = Card()
        self.status = QLabel("Pronto para começar.")
        self.status.setObjectName("muted")
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setFixedHeight(12)
        self.result = QLabel()
        self.result.setObjectName("banner")
        self.result.setWordWrap(True)
        self.result.setVisible(False)
        actions = QHBoxLayout()
        self.btn_open = QPushButton("Abrir pasta de saída")
        self.btn_open.setObjectName("link")
        self.btn_open.setVisible(False)
        self.btn_review = QPushButton("Revisar legendas agora")
        self.btn_review.setObjectName("link")
        self.btn_review.setVisible(False)
        self.btn_log = QPushButton("Mostrar detalhes")
        self.btn_log.setObjectName("link")
        actions.addWidget(self.btn_review)
        actions.addWidget(self.btn_open)
        actions.addWidget(self.btn_log)
        actions.addStretch(1)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("danger")
        self.btn_cancel.setVisible(False)
        self.btn_start = QPushButton("Iniciar processamento")
        self.btn_start.setObjectName("primary")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        actions.addWidget(self.btn_cancel)
        actions.addWidget(self.btn_start)
        self.log = QPlainTextEdit()
        self.log.setObjectName("code")
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(140)
        self.log.setVisible(False)
        prog_card.body.addWidget(self.status)
        prog_card.body.addWidget(self.progress)
        prog_card.body.addWidget(self.result)
        prog_card.body.addWidget(self.log)
        prog_card.body.addLayout(actions)
        left.addWidget(prog_card)

        # ---- coluna direita: modo + opcoes
        opts = QWidget()
        ol = QVBoxLayout(opts)
        ol.setContentsMargins(0, 0, 6, 0)
        ol.setSpacing(12)

        mode = Card("Modo")
        self.preset = QComboBox()
        self.preset.addItems([*state.PRESETS.keys(), state.CUSTOM])
        self.preset_hint = hint("")
        mode.body.addWidget(self.preset)
        mode.body.addWidget(self.preset_hint)
        ol.addWidget(mode)

        cut = Card("Corte e voz")
        self.o_autocut = toggle("Cortar pausas", "Encurta os silêncios entre as falas (revisável na linha do tempo)")
        self.o_fillers = toggle("Cortar vícios (é…, ãh, hum)", "Também sugere “né” e “tipo”, desmarcados")
        self.o_pause = QDoubleSpinBox()
        self.o_pause.setRange(1.0, 60.0)
        self.o_pause.setSingleStep(0.5)
        self.o_pause.setSuffix(" s")
        self.o_pause.setDecimals(1)
        self.o_pause.setFixedWidth(96)
        self.o_edl = toggle("Exportar timeline EDL", "Para abrir os cortes no DaVinci Resolve ou Premiere")
        self.o_master = toggle("Masterizar voz (-14 LUFS)", "Equalização e volume no padrão do YouTube")
        cut.body.addWidget(self.o_autocut)
        cut.body.addWidget(self.o_fillers)
        cut.body.addWidget(row(QLabel("Manter pausas maiores que"), self.o_pause))
        cut.body.addWidget(self.o_edl)
        cut.body.addWidget(self.o_master)
        ol.addWidget(cut)

        leg = Card("Legendas")
        self.o_review = toggle("Revisar legendas antes de gerar o vídeo",
                               "Para depois da transcrição para você corrigir o texto na tela Legendas")
        self.o_vocab = QLineEdit()
        self.o_vocab.setPlaceholderText("Ex.: Vygotsky, LGPD, Bhaskara")
        self.o_vocab.setToolTip("Nomes, siglas e termos técnicos da aula, separados por vírgula. "
                                "Ajudam o Whisper a escrever certo.")
        leg.body.addWidget(self.o_review)
        leg.body.addWidget(QLabel("Vocabulário da aula"))
        leg.body.addWidget(self.o_vocab)
        leg.body.addWidget(hint("O estilo (fonte, cores, karaokê) fica na tela Estilo das legendas."))
        ol.addWidget(leg)

        vid = Card("Vídeo")
        self.o_hardsub = toggle("Queimar legenda no vídeo")
        self.o_shorts = toggle("Gerar legenda versão Shorts")
        self.o_encoder = QComboBox()
        for label, _ in ENCODERS:
            self.o_encoder.addItem(label)
        vid.body.addWidget(self.o_hardsub)
        vid.body.addWidget(self.o_shorts)
        vid.body.addWidget(QLabel("Aceleração de vídeo"))
        vid.body.addWidget(self.o_encoder)
        ol.addWidget(vid)

        mat = Card("Material didático")
        self.o_slides = toggle("Detectar slides do vídeo")
        self.o_handout = toggle("Apostila ilustrada (HTML)")
        self.o_pdf = toggle("Apostila em PDF")
        for w in (self.o_slides, self.o_handout, self.o_pdf):
            mat.body.addWidget(w)
        ol.addWidget(mat)

        ia = Card("IA local (Ollama)")
        self.o_summary = toggle("Resumo executivo")
        self.o_quiz = toggle("Quiz de fixação")
        self.o_clips = toggle("Cortes 9:16 para redes")
        self.o_clips_n = QSpinBox()
        self.o_clips_n.setRange(1, 10)
        self.o_clips_n.setFixedWidth(96)
        for w in (self.o_summary, self.o_quiz, self.o_clips):
            ia.body.addWidget(w)
        ia.body.addWidget(row(QLabel("Quantidade de cortes"), self.o_clips_n))
        ia.body.addWidget(hint("Sem o Ollama aberto, essas opções viram aviso e o resto é feito normalmente."))
        ol.addWidget(ia)
        ol.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(opts)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(330)
        scroll.setMaximumWidth(380)
        body.addWidget(scroll, 0)

        # ---- sinais
        self.btn_add.clicked.connect(self._pick_files)
        self.btn_add_dir.clicked.connect(self._pick_dir)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear.clicked.connect(self._clear)
        self.drop.dropped.connect(self.add_paths)
        self.btn_out.clicked.connect(self._pick_out)
        # lambda: o sinal clicked() envia um bool que nao pode cair no parametro `only`
        self.btn_start.clicked.connect(lambda _checked=False: self.start())
        self.btn_cancel.clicked.connect(self.cancel)
        self.btn_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.out_edit.text())))
        self.btn_log.clicked.connect(self._toggle_log)
        self.btn_review.clicked.connect(self._request_review)
        self.preset.currentTextChanged.connect(self._apply_preset)
        for w in self._option_widgets():
            sig = getattr(w, "toggled", None) or getattr(w, "valueChanged", None) or w.currentIndexChanged
            sig.connect(self._on_option_changed)
        self.o_autocut.toggled.connect(self._sync_enabled)
        self.o_fillers.toggled.connect(self._sync_enabled)
        self.o_slides.toggled.connect(self._sync_enabled)
        self.o_handout.toggled.connect(self._sync_enabled)
        self.o_clips.toggled.connect(self._sync_enabled)
        self._refresh_queue()

    def _option_widgets(self) -> list[QWidget]:
        return [self.o_autocut, self.o_fillers, self.o_pause, self.o_edl, self.o_master, self.o_hardsub, self.o_shorts,
                self.o_encoder, self.o_slides, self.o_handout, self.o_pdf, self.o_summary, self.o_quiz,
                self.o_clips, self.o_clips_n]

    # ------------------------------------------------------------------ opcoes
    def options(self) -> dict[str, Any]:
        """Escolhas da tela no formato do Settings."""
        clips = self.o_clips.isChecked()
        return {
            "autocut": {"enabled": False},
            "cleanup": {"enabled": self.o_autocut.isChecked() or self.o_fillers.isChecked(),
                        "pauses": self.o_autocut.isChecked(), "fillers": self.o_fillers.isChecked(),
                        "export_edl": self.o_edl.isChecked(), "max_pause_s": self.o_pause.value()},
            "audio": {"master": self.o_master.isChecked()},
            "render": {"hardsub": self.o_hardsub.isChecked(), "encoder": ENCODERS[self.o_encoder.currentIndex()][1]},
            "subtitles": {"shorts_version": self.o_shorts.isChecked(), "review": self.o_review.isChecked()},
            "whisper": {"vocabulary": [t.strip() for t in self.o_vocab.text().split(",") if t.strip()]},
            "slides": {"enabled": self.o_slides.isChecked(), "handout": self.o_handout.isChecked(),
                       "handout_pdf": self.o_handout.isChecked() and self.o_pdf.isChecked()},
            "llm": {"enabled": self.o_summary.isChecked() or self.o_quiz.isChecked() or clips,
                    "summary": self.o_summary.isChecked(), "quiz": self.o_quiz.isChecked(),
                    "clips": clips, "clips_count": self.o_clips_n.value()},
        }

    def _set_options(self, s) -> None:
        self._loading = True
        try:
            self.o_autocut.setChecked(s.cleanup.enabled and s.cleanup.pauses)
            self.o_fillers.setChecked(s.cleanup.enabled and s.cleanup.fillers)
            self.o_pause.setValue(s.cleanup.max_pause_s)
            self.o_edl.setChecked(s.cleanup.export_edl)
            self.o_master.setChecked(s.audio.master)
            self.o_hardsub.setChecked(s.render.hardsub)
            self.o_shorts.setChecked(s.subtitles.shorts_version)
            self.o_encoder.setCurrentIndex(next((i for i, (_, v) in enumerate(ENCODERS) if v == s.render.encoder.value), 0))
            self.o_slides.setChecked(s.slides.enabled)
            self.o_handout.setChecked(s.slides.handout)
            self.o_pdf.setChecked(s.slides.handout_pdf)
            on = s.llm.enabled
            self.o_summary.setChecked(on and s.llm.summary)
            self.o_quiz.setChecked(on and s.llm.quiz)
            self.o_clips.setChecked(on and s.llm.clips)
            self.o_clips_n.setValue(s.llm.clips_count)
        finally:
            self._loading = False
        self._sync_enabled()

    def _apply_preset(self, label: str) -> None:
        self.preset_hint.setText(state.PRESET_HINTS.get(label, ""))
        if self._loading or label == state.CUSTOM:
            return
        path = builtin_profiles().get(state.PRESETS[label])
        if path:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            data.pop("profile_name", None)
            self._set_options(state.compose(state.load_base_settings(), data))

    def _on_option_changed(self, *_) -> None:
        if self._loading:
            return
        self._loading = True
        self.preset.setCurrentText(state.CUSTOM)
        self.preset_hint.setText(state.PRESET_HINTS[state.CUSTOM])
        self._loading = False

    def _sync_enabled(self, *_) -> None:
        self.o_pause.setEnabled(self.o_autocut.isChecked())
        self.o_edl.setEnabled(self.o_autocut.isChecked() or self.o_fillers.isChecked())
        self.o_pdf.setEnabled(self.o_handout.isChecked())
        self.o_clips_n.setEnabled(self.o_clips.isChecked())

    # ------------------------------------------------------------------ fila
    def add_paths(self, paths: list[Path]) -> None:
        new = []
        for p in paths:
            files = sorted(f for f in p.rglob("*") if f.suffix.lower() in VIDEO_EXT) if p.is_dir() else [p]
            for f in files:
                f = f.resolve()
                if f.suffix.lower() in VIDEO_EXT and f not in self.paths and not f.stem.endswith(("_DINAMICO", "_LEGENDADO")):
                    self.paths.append(f)
                    new.append(f)
        for f in new:
            r = self.table.rowCount()
            self.table.insertRow(r)
            item = QTableWidgetItem(f.name)
            item.setToolTip(str(f))
            self.table.setItem(r, COL_NAME, item)
            for c, t in ((COL_DUR, "…"), (COL_STAGE, ""), (COL_STATUS, "Na fila")):
                self.table.setItem(r, c, QTableWidgetItem(t))
            run_task(lambda _p, f=f: ff.probe(f).duration,
                     on_done=lambda d, f=f: self._set_cell(f, COL_DUR, fmt_duration(d)),
                     on_error=lambda e, f=f: self._set_cell(f, COL_STATUS, "Inválido", theme.DANGER, e))
        if new and not self.out_edit.text():
            self.out_edit.setText(str(new[0].parent / "LUIS MEDIA - resultado"))
        self._refresh_queue()

    def _row_of(self, f: Path) -> int:
        try:
            return self.paths.index(f)
        except ValueError:
            return -1

    def _set_cell(self, f: Path, col: int, text: str, color: str | None = None, tip: str = "") -> None:
        r = self._row_of(f)
        if r < 0:
            return
        item = self.table.item(r, col)
        if item is None:
            item = QTableWidgetItem()
            self.table.setItem(r, col, item)
        item.setText(text)
        item.setForeground(QColor(color or theme.TEXT))
        item.setToolTip(tip)

    def _pick_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Escolher vídeos", self._last_dir(),
                                                "Vídeos (*.mp4 *.mkv *.mov *.m4v *.webm)")
        self.add_paths([Path(f) for f in files])

    def _pick_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Escolher pasta com vídeos", self._last_dir())
        if d:
            self.add_paths([Path(d)])

    def _pick_out(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Pasta de saída", self.out_edit.text() or self._last_dir())
        if d:
            self.out_edit.setText(d)

    def _last_dir(self) -> str:
        if self.paths:
            return str(self.paths[-1].parent)
        return QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MoviesLocation)

    def _remove_selected(self) -> None:
        for r in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(r)
            del self.paths[r]
        self._refresh_queue()

    def _clear(self) -> None:
        self.table.setRowCount(0)
        self.paths.clear()
        self._refresh_queue()

    def _refresh_queue(self) -> None:
        n = len(self.paths)
        self.lbl_queue.setText(f"Fila de vídeos ({n})" if n else "Fila de vídeos")
        self.empty_hint.setVisible(n == 0)
        self.queue_changed.emit(self.paths[0] if self.paths else None)
        self.table.setVisible(n > 0)
        busy = self.job is not None
        self.btn_start.setEnabled(n > 0 and not busy)
        for b in (self.btn_add, self.btn_add_dir, self.btn_remove, self.btn_clear):
            b.setEnabled(not busy)

    # ------------------------------------------------------------------ execucao
    def start(self, only: list[Path] | None = None, overrides: dict | None = None) -> None:
        """Processa a fila (ou so ``only``). ``overrides`` (tela Inicio) vale por cima das opcoes."""
        if not self.paths or self.job:
            return
        videos = [p for p in self.paths if only is None or p in only]
        if overrides is None:  # continuacao depois da revisao: repete as escolhas da tela Inicio
            overrides = next((self._overrides[v] for v in videos if v in self._overrides), None)
        for v in videos:
            if overrides is not None:
                self._overrides[v] = overrides
        out = self.out_edit.text().strip()
        if not out:
            QMessageBox.warning(self, "Pasta de saída", "Escolha onde salvar os resultados.")
            return
        try:
            settings = state.compose(state.compose(state.load_base_settings(), self.options()), overrides or {})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Configuração inválida", str(exc))
            return
        self._save_ui()
        for f in videos:
            self._set_cell(f, COL_STAGE, "")
            self._set_cell(f, COL_STATUS, "Na fila")
        self.log.clear()
        banner(self.result, "info", "")
        self.btn_open.setVisible(False)
        self.progress.setValue(0)
        self.status.setText("Preparando…")
        self.btn_review.setVisible(False)
        self.job = PipelineJob(settings, videos, Path(out))
        self.job.signals.event.connect(self._on_event)
        self.job.signals.finished.connect(self._on_finished)
        self.job.signals.failed.connect(self._on_failed)
        self.btn_cancel.setVisible(True)
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setText("Cancelar")
        self._refresh_queue()
        self.busy_changed.emit(True)
        self.job_started.emit(self.job)
        start_job(self.job)

    def cancel(self) -> None:
        if self.job:
            self.job.cancel()
            self.btn_cancel.setEnabled(False)
            self.btn_cancel.setText("Cancelando…")
            self.status.setText("Cancelando… o que já ficou pronto será mantido.")

    def _on_event(self, e: dict) -> None:
        total, idx = max(1, e.get("total") or 1), max(1, e.get("index") or 1)
        stage = e["stage"]
        pos = STAGE_ORDER.index(stage) if stage in STAGE_ORDER else 0
        frac = (pos + min(1.0, float(e.get("progress") or 0))) / len(STAGE_ORDER)
        self.progress.setValue(int(1000 * ((idx - 1) + frac) / total))
        name = STAGE_NAMES.get(stage, stage)
        jobs = self.job.videos if self.job else self.paths
        f = jobs[idx - 1] if idx - 1 < len(jobs) else None
        pct = f" {float(e['progress']):.0%}" if e["status"] == "running" and e.get("progress") else ""
        self.status.setText(f"Vídeo {idx} de {total} · {e['video']} · {name}{pct}")
        if f is not None:
            self._set_cell(f, COL_STAGE, name + pct)
            if e["status"] == "running":
                self._set_cell(f, COL_STATUS, "Processando", theme.ACCENT)
            elif e["status"] == "failed":
                self._set_cell(f, COL_STATUS, "Aviso" if stage not in ("autocut", "audio", "transcricao", "validacao") else "Falhou",
                               theme.WARNING, e.get("message", ""))
        if e["status"] in ("done", "failed", "skipped"):
            msg = f" — {e['message']}" if e.get("message") else ""
            self.log.appendPlainText(f"[{idx}/{total}] {e['video']}: {name} → {e['status']}{msg}")

    def _finish_ui(self) -> None:
        self.job = None
        self.btn_cancel.setVisible(False)
        self._refresh_queue()
        self.busy_changed.emit(False)

    def _on_finished(self, results: list[dict]) -> None:
        cancelled = self.job.cancelled if self.job else False
        self._finish_ui()
        ok = [r for r in results if r["ok"]]
        bad = [r for r in results if not r["ok"]]
        review = [r for r in results if r["ok"] and r.get("needs_review")]
        ok = [r for r in ok if not r.get("needs_review")]
        for r in results:
            f = Path(r["source"])
            if r["ok"] and r.get("needs_review"):
                self._set_cell(f, COL_STATUS, "Revisar legendas", theme.ACCENT)
                self._set_cell(f, COL_STAGE, "Aguardando você")
            elif r["ok"]:
                warn = len(r["warnings"])
                self._set_cell(f, COL_STATUS, "Concluído" if not warn else f"OK ({warn} aviso{'s' if warn > 1 else ''})",
                               theme.SUCCESS if not warn else theme.WARNING, "\n".join(r["warnings"]))
                self._set_cell(f, COL_STAGE, "—")
            else:
                self._set_cell(f, COL_STATUS, "Falhou", theme.DANGER, r.get("error") or "")
                self._set_cell(f, COL_STAGE, STAGE_NAMES.get(r.get("failed_stage") or "", ""))
        self.progress.setValue(1000 if not cancelled else self.progress.value())
        self.btn_open.setVisible(True)
        if cancelled:
            banner(self.result, "warn", "Processamento cancelado. O que já ficou pronto foi mantido; "
                                        "rodar de novo continua de onde parou.")
            self.status.setText("Cancelado.")
            return
        warnings = sum(len(r["warnings"]) for r in ok)
        self._review_target = (self.out_edit.text(), Path(review[0]["source"]).stem) if review else None
        self.btn_review.setVisible(bool(review))
        if review and not bad:
            done = f"{len(ok)} pronto(s). " if ok else ""
            banner(self.result, "info", f"{done}{len(review)} vídeo(s) aguardando a revisão das legendas. "
                                        "Clique em Revisar legendas agora.")
            self.status.setText("Aguardando revisão.")
            return
        if not bad:
            text = f"{len(ok)} vídeo(s) processado(s) com sucesso."
            if warnings:
                text += f" {warnings} aviso(s): passe o mouse no status para ver."
            banner(self.result, "ok" if not warnings else "warn", text)
        else:
            lines = "\n".join(f"• {Path(r['source']).name}: {r.get('error')}" for r in bad)
            banner(self.result, "error", f"{len(ok)} ok e {len(bad)} com falha:\n{lines}")
        self.status.setText("Concluído.")

    def _request_review(self) -> None:
        if getattr(self, "_review_target", None):
            self.review_requested.emit(*self._review_target)

    def continue_after_review(self, sources: list[Path]) -> None:
        """Chamado pelo editor: gera o video legendado e os cortes so dos aprovados."""
        for s in sources:
            if s not in self.paths:
                self.add_paths([s])
        self.start(only=sources)

    def _on_failed(self, msg: str) -> None:
        self._finish_ui()
        banner(self.result, "error", f"O processamento parou: {msg}")
        self.status.setText("Erro.")

    def _toggle_log(self) -> None:
        vis = not self.log.isVisible()
        self.log.setVisible(vis)
        self.btn_log.setText("Ocultar detalhes" if vis else "Mostrar detalhes")

    # ------------------------------------------------------------------ estado
    def _save_ui(self) -> None:
        ui = state.load_ui()
        ui.update({"preset": self.preset.currentText(), "options": self.options(), "out": self.out_edit.text(),
                   "review": self.o_review.isChecked(), "vocab": self.o_vocab.text()})
        state.save_ui(ui)

    def _restore(self) -> None:
        ui = state.load_ui()
        label = ui.get("preset") or "Curso completo"
        if label == state.CUSTOM and ui.get("options"):
            try:
                self._set_options(state.compose(state.load_base_settings(), ui["options"]))
            except Exception:  # noqa: BLE001 - estado antigo invalido: volta ao padrao
                label = "Curso completo"
        self._loading = True
        self.preset.setCurrentText(label if label in [*state.PRESETS, state.CUSTOM] else "Curso completo")
        self._loading = False
        if self.preset.currentText() != state.CUSTOM:
            self._apply_preset(self.preset.currentText())
        self.preset_hint.setText(state.PRESET_HINTS.get(self.preset.currentText(), ""))
        if ui.get("out"):
            self.out_edit.setText(ui["out"])
        self.o_review.setChecked(bool(ui.get("review")))
        self.o_vocab.setText(ui.get("vocab", ""))

    def debug_state(self) -> str:  # usado nos testes
        return json.dumps(self.options(), sort_keys=True)
