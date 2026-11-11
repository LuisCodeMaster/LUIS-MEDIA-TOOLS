"""Paginas secundarias: Slides com IA, Diagnostico e Configuracoes."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..adapters.ollama import OllamaClient
from ..core.config import Settings
from ..diagnostics import run_checks
from ..stages import presentation
from . import state, theme
from .tasks import run_task
from .widgets import Card, banner, hint, page_header, row, toggle

EXEMPLO_MD = """# Funções do 1º grau
### Do gráfico à aplicação
**Prof. Luis**
---
## O que é uma função?
- Uma regra que liga cada **x** a um único **y**
- Notação: `f(x) = ax + b`
[DICA] Pense numa máquina: entra x, sai f(x).
---
## Coeficientes
|| COLUNA
**a**: inclinação da reta
|| COLUNA
**b**: onde a reta corta o eixo y
|| FIM
[NOTA] Desenhar duas retas com o mesmo b e a diferente.
"""


def _page() -> tuple[QWidget, QVBoxLayout]:
    w = QWidget()
    w.setObjectName("page")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(28, 22, 28, 18)
    lay.setSpacing(14)
    return w, lay


class SlidesPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")
        page, lay = _page()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        lay.addWidget(page_header("Slides com IA",
                                  "Escreva o tema, deixe a IA montar o roteiro, ajuste o texto e gere uma "
                                  "apresentação 16:9 interativa que abre no navegador."))

        top = Card("Tema da aula")
        self.topic = QLineEdit()
        self.topic.setPlaceholderText("Ex.: Introdução a funções do 1º grau para o 9º ano")
        self.btn_ai = QPushButton("Gerar roteiro com IA")
        self.btn_ai.setObjectName("primary")
        top.body.addWidget(row(self.topic, self.btn_ai, stretch_last=True))
        self.msg = QLabel()
        self.msg.setObjectName("banner")
        self.msg.setWordWrap(True)
        self.msg.setVisible(False)
        top.body.addWidget(self.msg)
        lay.addWidget(top)

        ed = Card("Roteiro (Markdown)")
        self.editor = QPlainTextEdit()
        self.editor.setObjectName("code")
        self.editor.setPlainText(EXEMPLO_MD)
        ed.body.addWidget(self.editor, 1)
        ed.body.addWidget(hint("--- separa os slides · # título · - tópicos · [DICA] [ATENCAO] [NOTA] · "
                               "|| COLUNA / || FIM · blocos ```código```. Na apresentação: setas, "
                               "L = laser, D = desenhar, O = visão geral, N = notas, P = imprimir/PDF."))
        bar = QHBoxLayout()
        self.btn_open = QPushButton("Abrir .md…")
        self.btn_save = QPushButton("Salvar .md…")
        self.btn_build = QPushButton("Gerar apresentação")
        self.btn_build.setObjectName("primary")
        bar.addWidget(self.btn_open)
        bar.addWidget(self.btn_save)
        bar.addStretch(1)
        bar.addWidget(self.btn_build)
        ed.body.addLayout(bar)
        lay.addWidget(ed, 1)

        self.btn_ai.clicked.connect(self._generate)
        self.btn_open.clicked.connect(self._open_md)
        self.btn_save.clicked.connect(self._save_md)
        self.btn_build.clicked.connect(self._build)

    def _generate(self) -> None:
        topic = self.topic.text().strip()
        if not topic:
            banner(self.msg, "warn", "Escreva o tema da aula primeiro.")
            return
        client = OllamaClient(state.load_base_settings().llm)
        self.btn_ai.setEnabled(False)
        self.btn_ai.setText("Gerando…")
        banner(self.msg, "info", "A IA está escrevendo o roteiro. Leva de 20 s a 2 min no computador.")

        def work(_p):
            if not client.is_running():
                raise RuntimeError("O Ollama não está aberto. Abra o Ollama e tente de novo.")
            return presentation.generate_markdown(client, topic)

        run_task(work, on_done=self._generated, on_error=self._gen_failed)

    def _generated(self, md: str) -> None:
        self.editor.setPlainText(md)
        self.btn_ai.setEnabled(True)
        self.btn_ai.setText("Gerar roteiro com IA")
        banner(self.msg, "ok", "Roteiro pronto. Revise o texto e clique em Gerar apresentação.")

    def _gen_failed(self, err: str) -> None:
        self.btn_ai.setEnabled(True)
        self.btn_ai.setText("Gerar roteiro com IA")
        banner(self.msg, "error", err)

    def _open_md(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "Abrir roteiro", "", "Markdown (*.md *.txt)")
        if f:
            self.editor.setPlainText(Path(f).read_text(encoding="utf-8-sig"))

    def _save_md(self) -> Path | None:
        f, _ = QFileDialog.getSaveFileName(self, "Salvar roteiro", self._default_name(".md"), "Markdown (*.md)")
        if not f:
            return None
        p = Path(f)
        p.write_text(self.editor.toPlainText(), encoding="utf-8")
        return p

    def _default_name(self, ext: str) -> str:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        name = "".join(c if c.isalnum() or c in " -_" else "" for c in (self.topic.text() or "apresentacao"))
        return str(Path(base) / f"{name.strip()[:60] or 'apresentacao'}{ext}")

    def _build(self) -> None:
        text = self.editor.toPlainText().strip()
        if not text:
            banner(self.msg, "warn", "O roteiro está vazio.")
            return
        f, _ = QFileDialog.getSaveFileName(self, "Salvar apresentação", self._default_name(".html"),
                                           "Página HTML (*.html)")
        if not f:
            return
        html_path = Path(f)
        md_path = html_path.with_suffix(".md")
        md_path.write_text(text, encoding="utf-8")
        out = presentation.build_slides(str(md_path), html_path)
        banner(self.msg, "ok", f"Apresentação salva em {out}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(out)))


class DiagnosticsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")
        page, lay = _page()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        lay.addWidget(page_header("Diagnóstico",
                                  "Confere se tudo o que o programa usa está pronto neste computador."))
        self.summary = QLabel()
        self.summary.setObjectName("banner")
        self.summary.setWordWrap(True)
        self.summary.setVisible(False)
        lay.addWidget(self.summary)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Componente", "Situação", "Detalhes / como resolver"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setShowGrid(False)
        self.table.setWordWrap(True)
        hh = self.table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table, 1)

        bar = QHBoxLayout()
        self.btn_check = QPushButton("Verificar novamente")
        self.btn_pull = QPushButton("Baixar modelo de IA")
        self.pull_bar = QProgressBar()
        self.pull_bar.setRange(0, 1000)
        self.pull_bar.setFixedWidth(220)
        self.pull_bar.setVisible(False)
        bar.addWidget(self.btn_check)
        bar.addWidget(self.btn_pull)
        bar.addWidget(self.pull_bar)
        bar.addStretch(1)
        lay.addLayout(bar)
        self.btn_check.clicked.connect(self.refresh)
        self.btn_pull.clicked.connect(self._pull)
        self._ran = False

    def showEvent(self, e) -> None:  # noqa: N802
        super().showEvent(e)
        if not self._ran:
            self._ran = True
            self.refresh()

    def refresh(self) -> None:
        self.btn_check.setEnabled(False)
        banner(self.summary, "info", "Verificando… (o teste das placas de vídeo leva alguns segundos)")
        settings = state.load_base_settings()
        run_task(lambda _p: run_checks(settings), on_done=self._show, on_error=self._failed)

    def _show(self, checks) -> None:
        self.btn_check.setEnabled(True)
        self.table.setRowCount(0)
        for c in checks:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(c.name))
            if c.ok:
                status, color = "● Pronto", theme.SUCCESS
            elif c.essential:
                status, color = "● Falta", theme.DANGER
            else:
                status, color = "● Opcional", theme.MUTED
            it = QTableWidgetItem(status)
            it.setForeground(QColor(color))
            self.table.setItem(r, 1, it)
            self.table.setItem(r, 2, QTableWidgetItem(c.info if c.ok else f"{c.info}\n{c.fix}".strip()))
        self.table.resizeRowsToContents()
        missing = [c.name for c in checks if c.essential and not c.ok]
        model_missing = any(c.name.startswith("Modelo ") and not c.ok for c in checks)
        ollama_up = any(c.name.startswith("Ollama") and c.ok for c in checks)
        self.btn_pull.setVisible(ollama_up and model_missing)
        if missing:
            banner(self.summary, "error", "Falta: " + ", ".join(missing) + ". Rode o Instalar.cmd de novo.")
        else:
            banner(self.summary, "ok", "Tudo pronto para processar. Itens opcionais só ativam recursos extras.")

    def _failed(self, err: str) -> None:
        self.btn_check.setEnabled(True)
        banner(self.summary, "error", f"Não consegui verificar: {err}")

    def _pull(self) -> None:
        client = OllamaClient(state.load_base_settings().llm)
        self.btn_pull.setEnabled(False)
        self.pull_bar.setVisible(True)
        self.pull_bar.setValue(0)
        run_task(lambda prog: client.pull_model(prog),
                 on_done=lambda _r: (self.pull_bar.setVisible(False), self.btn_pull.setEnabled(True), self.refresh()),
                 on_error=lambda e: (self.pull_bar.setVisible(False), self.btn_pull.setEnabled(True),
                                     banner(self.summary, "error", f"Falha ao baixar: {e}")),
                 on_progress=lambda f: self.pull_bar.setValue(int(f * 1000)))


WHISPER_MODELS = [("tiny", "Rapidíssimo, menos preciso"), ("base", "Rápido"), ("small", "Equilibrado"),
                  ("medium", "Preciso (recomendado)"), ("large-v3", "Máxima precisão, lento na CPU")]
LANGS = [("pt", "Português"), ("en", "Inglês"), ("es", "Espanhol")]
DEVICES = [("auto", "Automático"), ("cpu", "CPU"), ("cuda", "GPU NVIDIA (CUDA)")]


class SettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")
        page, lay = _page()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        lay.addWidget(page_header("Configurações",
                                  "Valem para todos os processamentos. Os modos da tela Processar ficam por cima."))
        cols = QHBoxLayout()
        cols.setSpacing(16)
        lay.addLayout(cols)

        tr = Card("Transcrição (Whisper)")
        f1 = QFormLayout()
        self.w_model = QComboBox()
        for m, d in WHISPER_MODELS:
            self.w_model.addItem(f"{m} — {d}", m)
        self.w_lang = QComboBox()
        for code, name in LANGS:
            self.w_lang.addItem(name, code)
        self.w_device = QComboBox()
        for code, name in DEVICES:
            self.w_device.addItem(name, code)
        f1.addRow("Modelo", self.w_model)
        f1.addRow("Idioma da aula", self.w_lang)
        f1.addRow("Processar em", self.w_device)
        tr.body.addLayout(f1)
        tr.body.addWidget(hint("O modelo é baixado automaticamente na primeira transcrição."))

        ia = Card("IA local (Ollama)")
        f2 = QFormLayout()
        self.l_model = QComboBox()
        self.l_model.setEditable(True)
        self.l_model.addItems(["llama3.2:3b", "qwen2.5:3b", "gemma2:2b", "llama3.1:8b"])
        self.l_url = QLineEdit()
        f2.addRow("Modelo", self.l_model)
        f2.addRow("Endereço", self.l_url)
        ia.body.addLayout(f2)
        ia.body.addWidget(hint("Modelos maiores escrevem melhor, mas precisam de mais memória."))

        left = QVBoxLayout()
        left.addWidget(tr)
        left.addWidget(ia)
        left.addStretch(1)

        av = Card("Vídeo, áudio e entrega")
        f3 = QFormLayout()
        self.crf = QSpinBox()
        self.crf.setRange(16, 32)
        self.crf.setFixedWidth(120)
        self.crf.setToolTip("Menor = melhor qualidade e arquivo maior. 20 é um bom padrão.")
        self.lufs = QDoubleSpinBox()
        self.lufs.setRange(-24, -9)
        self.lufs.setSingleStep(1)
        self.lufs.setDecimals(0)
        self.lufs.setSuffix(" LUFS")
        self.lufs.setFixedWidth(120)
        f3.addRow("Qualidade do vídeo (CRF)", self.crf)
        f3.addRow("Volume alvo", self.lufs)
        av.body.addLayout(f3)
        self.chapters = toggle("Gerar capítulos do YouTube")
        self.zip = toggle("Gerar Entregavel.zip")
        self.zip_videos = toggle("Incluir os vídeos no ZIP")
        self.keep_tmp = toggle("Manter arquivos temporários (diagnóstico)")
        for w in (self.chapters, self.zip, self.zip_videos, self.keep_tmp):
            av.body.addWidget(w)

        right = QVBoxLayout()
        right.addWidget(av)
        right.addStretch(1)
        cols.addLayout(left, 1)
        cols.addLayout(right, 1)
        lay.addStretch(1)

        bar = QHBoxLayout()
        self.saved = QLabel()
        self.saved.setObjectName("muted")
        self.btn_reset = QPushButton("Restaurar padrão")
        self.btn_save = QPushButton("Salvar configurações")
        self.btn_save.setObjectName("primary")
        bar.addWidget(self.saved)
        bar.addStretch(1)
        bar.addWidget(self.btn_reset)
        bar.addWidget(self.btn_save)
        lay.addLayout(bar)
        self.btn_save.clicked.connect(self.save)
        self.btn_reset.clicked.connect(lambda: self._load(Settings()))
        self.zip.toggled.connect(self.zip_videos.setEnabled)
        self._load(state.load_base_settings())

    def _load(self, s: Settings) -> None:
        def pick(combo: QComboBox, value: str) -> None:
            i = combo.findData(value)
            combo.setCurrentIndex(i if i >= 0 else 0)

        pick(self.w_model, s.whisper.model)
        pick(self.w_lang, s.whisper.language)
        pick(self.w_device, s.whisper.device.value)
        self.l_model.setCurrentText(s.llm.model)
        self.l_url.setText(s.llm.base_url)
        self.crf.setValue(s.render.crf)
        self.lufs.setValue(s.audio.target_lufs)
        self.chapters.setChecked(s.output.chapters)
        self.zip.setChecked(s.output.zip_package)
        self.zip_videos.setChecked(s.output.zip_include_videos)
        self.zip_videos.setEnabled(s.output.zip_package)
        self.keep_tmp.setChecked(s.keep_intermediates)
        self.saved.setText("")

    def values(self) -> dict:
        return {
            "whisper": {"model": self.w_model.currentData(), "language": self.w_lang.currentData(),
                        "device": self.w_device.currentData()},
            "llm": {"model": self.l_model.currentText().strip(), "base_url": self.l_url.text().strip()},
            "render": {"crf": self.crf.value()},
            "audio": {"target_lufs": self.lufs.value()},
            "output": {"chapters": self.chapters.isChecked(), "zip_package": self.zip.isChecked(),
                       "zip_include_videos": self.zip_videos.isChecked()},
            "keep_intermediates": self.keep_tmp.isChecked(),
        }

    def save(self) -> None:
        try:
            s = state.compose(state.load_base_settings(), self.values())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Valor inválido", str(exc))
            return
        state.save_base_settings(s)
        self.saved.setText("Configurações salvas.")


def ollama_version(url: str) -> str | None:
    """Usado na barra lateral para mostrar se a IA esta online."""
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/version", timeout=2) as r:
            return json.loads(r.read()).get("version")
    except Exception:  # noqa: BLE001
        return None


__all__ = ["DiagnosticsPage", "SettingsPage", "SlidesPage", "ollama_version", "Qt"]
