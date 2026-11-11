"""Janela principal do LUIS MEDIA TOOLS."""

from __future__ import annotations

import sys
from importlib import resources

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from . import state, theme
from .other_pages import DiagnosticsPage, SettingsPage, SlidesPage, ollama_version
from .process_page import ProcessPage
from .tasks import run_task

APP_NAME = "LUIS MEDIA TOOLS"


def app_icon() -> QIcon:
    return QIcon(str(resources.files("luismedia.gui") / "assets" / "icon.svg"))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.setMinimumSize(1100, 720)
        self.resize(1280, 800)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- barra lateral
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(232)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 20, 0, 16)
        sl.setSpacing(6)
        brand = QHBoxLayout()
        brand.setContentsMargins(20, 0, 16, 14)
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(QSize(38, 38)))
        names = QVBoxLayout()
        names.setSpacing(0)
        n1 = QLabel("LUIS MEDIA")
        n1.setObjectName("appName")
        n2 = QLabel("Pós-produção com IA local")
        n2.setObjectName("appTag")
        names.addWidget(n1)
        names.addWidget(n2)
        brand.addWidget(logo)
        brand.addSpacing(8)
        brand.addLayout(names)
        brand.addStretch(1)
        sl.addLayout(brand)

        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setCursor(Qt.CursorShape.PointingHandCursor)
        for label in ("Processar aulas", "Slides com IA", "Diagnóstico", "Configurações"):
            item = QListWidgetItem(label)
            item.setSizeHint(QSize(200, 42))
            self.nav.addItem(item)
        sl.addWidget(self.nav, 1)

        self.ai_status = QLabel("IA local: verificando…")
        self.ai_status.setObjectName("appTag")
        self.ai_status.setContentsMargins(20, 0, 16, 0)
        ver = QLabel(f"Versão {__version__}")
        ver.setObjectName("appTag")
        ver.setContentsMargins(20, 0, 16, 0)
        sl.addWidget(self.ai_status)
        sl.addWidget(ver)
        root.addWidget(side)

        # ---- paginas
        self.stack = QStackedWidget()
        self.process = ProcessPage()
        self.slides = SlidesPage()
        self.diag = DiagnosticsPage()
        self.settings = SettingsPage()
        for p in (self.process, self.slides, self.diag, self.settings):
            self.stack.addWidget(p)
        root.addWidget(self.stack, 1)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.process.busy_changed.connect(self._on_busy)

        self._ai_timer = QTimer(self)
        self._ai_timer.timeout.connect(self._check_ai)
        self._ai_timer.start(20_000)
        QTimer.singleShot(300, self._check_ai)

    def _check_ai(self) -> None:
        url = state.load_base_settings().llm.base_url
        run_task(lambda _p: ollama_version(url), on_done=self._show_ai)

    def _show_ai(self, version) -> None:
        if version:
            self.ai_status.setText("● IA local: online")
            self.ai_status.setStyleSheet(f"color: {theme.SUCCESS};")
        else:
            self.ai_status.setText("● IA local: offline")
            self.ai_status.setStyleSheet(f"color: {theme.MUTED};")
            self.ai_status.setToolTip("Abra o Ollama para usar resumo, quiz, cortes e slides com IA.")

    def _on_busy(self, busy: bool) -> None:
        title = APP_NAME + (" — processando…" if busy else "")
        self.setWindowTitle(title)

    def closeEvent(self, e) -> None:  # noqa: N802
        if self.process.job is not None:
            ans = QMessageBox.question(
                self, "Processamento em andamento",
                "Há um processamento em andamento. Cancelar e fechar?\n\n"
                "O que já ficou pronto é mantido; rodar de novo continua de onde parou.")
            if ans != QMessageBox.StandardButton.Yes:
                e.ignore()
                return
            self.process.cancel()
        e.accept()


def make_app(argv: list[str] | None = None) -> QApplication:
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("LuisCodeMaster")
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")
    app.setStyleSheet(theme.QSS)
    return app


def main() -> int:
    if sys.platform == "win32":
        try:  # icone proprio na barra de tarefas (sem isso aparece o do Python)
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LuisCodeMaster.LuisMediaTools")
        except Exception:  # noqa: BLE001
            pass
    if "--selftest" in sys.argv:
        return selftest()
    app = make_app()
    win = MainWindow()
    win.show()
    return app.exec()


def selftest() -> int:
    """Checagem usada no build do instalador: o .exe abre a janela e acha o FFmpeg embutido."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from ..adapters import ffmpeg as ff

    lines: list[str] = []
    out = print if sys.stdout is not None else (lambda *a: lines.append(" ".join(map(str, a))))
    app = make_app(["selftest"])
    win = MainWindow()
    win.show()
    app.processEvents()
    ok = True
    for name in ("ffmpeg", "ffprobe"):
        try:
            path = ff.find_binary(name)
        except Exception as exc:  # noqa: BLE001
            path, ok = f"ERRO: {exc}", False
        out(f"{name}: {path}")
    out("subtitles:", ff.has_filter("subtitles"))
    ok = ok and ff.has_filter("subtitles")
    out("selftest", "OK" if ok else "FALHOU")
    if lines:  # .exe sem console: grava o resultado ao lado do executavel
        log = os.environ.get("LUISMEDIA_SELFTEST_LOG", "selftest.log")
        with open(log, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    win.close()
    return 0 if ok else 1
