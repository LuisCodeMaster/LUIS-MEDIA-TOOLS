"""Estilo das legendas (estilo CapCut) com previa real renderizada pelo proprio libass."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontDatabase, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.style import BUNDLED_FONTS, PRESETS_H, PRESETS_V, SYSTEM_FONTS, SubtitleStyle, fonts_dir
from ..stages.media import render_style_preview
from . import state
from .tasks import run_task
from .widgets import Card, hint, page_header

CUSTOM = "Personalizado"
POSITIONS = [("bottom", "Embaixo"), ("middle", "No meio"), ("top", "Em cima")]
ANIMATIONS = [("none", "Nenhuma"), ("fade", "Surgir suave (fade)"), ("pop", "Pop (cresce rápido)")]
HIGHLIGHTS = [("none", "Sem destaque"), ("color", "Palavra falada colorida"),
              ("pop", "Palavra colorida + pop"), ("reveal", "Revelar palavra por palavra (karaokê)")]


def register_fonts() -> None:
    for f in fonts_dir().glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(f))


class ColorButton(QPushButton):
    changed = Signal(str)

    def __init__(self, color: str = "#FFFFFF") -> None:
        super().__init__()
        self.setFixedSize(46, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._pick)
        self.set_color(color)

    def set_color(self, color: str) -> None:
        self._color = color.upper()
        self.setStyleSheet(f"QPushButton {{ background: {self._color}; border: 1px solid #5b6178; border-radius: 6px; }}")
        self.setToolTip(self._color)

    def color(self) -> str:
        return self._color

    def _pick(self) -> None:
        c = QColorDialog.getColor(QColor(self._color), self, "Escolher cor")
        if c.isValid():
            self.set_color(c.name())
            self.changed.emit(self._color)


class StyleEditor(QWidget):
    """Controles de um estilo + previa. Usado duas vezes: 16:9 e 9:16."""

    def __init__(self, presets: dict[str, SubtitleStyle], vertical: bool) -> None:
        super().__init__()
        self.presets, self.vertical = presets, vertical
        self._loading = False
        self.background: Path | None = None
        self._tmp = Path(tempfile.mkdtemp(prefix="lmt_preview_"))
        self._seq = 0

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 8, 0, 0)
        root.setSpacing(16)

        # ---- controles
        ctrl = QWidget()
        form_l = QVBoxLayout(ctrl)
        form_l.setContentsMargins(0, 0, 6, 0)
        form_l.setSpacing(12)

        c0 = Card("Modelo")
        self.preset = QComboBox()
        self.preset.addItems([*presets.keys(), CUSTOM])
        c0.body.addWidget(self.preset)
        form_l.addWidget(c0)

        c1 = Card("Texto")
        f1 = QFormLayout()
        self.font = QComboBox()
        self.font.setEditable(True)
        self.font.addItems(BUNDLED_FONTS + SYSTEM_FONTS)
        self.size = QDoubleSpinBox()
        self.size.setRange(2, 15)
        self.size.setSingleStep(0.5)
        self.size.setSuffix(" %")
        self.size.setFixedWidth(110)
        self.bold = QCheckBox("Negrito")
        self.upper = QCheckBox("MAIÚSCULAS")
        self.color = ColorButton()
        self.words = QSpinBox()
        self.words.setRange(0, 12)
        self.words.setSpecialValueText("Automático")
        self.words.setFixedWidth(130)
        f1.addRow("Fonte", self.font)
        f1.addRow("Tamanho", self.size)
        f1.addRow("Cor do texto", self.color)
        f1.addRow("", self.bold)
        f1.addRow("", self.upper)
        f1.addRow("Palavras por legenda", self.words)
        c1.body.addLayout(f1)
        form_l.addWidget(c1)

        c2 = Card("Contorno, sombra e caixa")
        f2 = QFormLayout()
        self.outline_color = ColorButton("#000000")
        self.outline = QDoubleSpinBox()
        self.outline.setRange(0, 12)
        self.outline.setSingleStep(0.5)
        self.outline.setFixedWidth(110)
        self.shadow = QDoubleSpinBox()
        self.shadow.setRange(0, 10)
        self.shadow.setSingleStep(0.5)
        self.shadow.setFixedWidth(110)
        self.glow = QDoubleSpinBox()
        self.glow.setRange(0, 10)
        self.glow.setSingleStep(0.5)
        self.glow.setFixedWidth(110)
        self.box = QCheckBox("Caixa de fundo")
        self.box_color = ColorButton("#000000")
        self.box_opacity = QSpinBox()
        self.box_opacity.setRange(0, 100)
        self.box_opacity.setSuffix(" %")
        self.box_opacity.setFixedWidth(110)
        f2.addRow("Cor do contorno", self.outline_color)
        f2.addRow("Espessura do contorno", self.outline)
        f2.addRow("Sombra", self.shadow)
        f2.addRow("Brilho (neon)", self.glow)
        f2.addRow("", self.box)
        f2.addRow("Cor da caixa", self.box_color)
        f2.addRow("Opacidade da caixa", self.box_opacity)
        c2.body.addLayout(f2)
        form_l.addWidget(c2)

        c3 = Card("Posição e animação")
        f3 = QFormLayout()
        self.position = QComboBox()
        for _, label in POSITIONS:
            self.position.addItem(label)
        self.margin = QDoubleSpinBox()
        self.margin.setRange(0, 45)
        self.margin.setSuffix(" %")
        self.margin.setFixedWidth(110)
        self.animation = QComboBox()
        for _, label in ANIMATIONS:
            self.animation.addItem(label)
        self.highlight = QComboBox()
        for _, label in HIGHLIGHTS:
            self.highlight.addItem(label)
        self.highlight_color = ColorButton("#FFE600")
        f3.addRow("Posição", self.position)
        f3.addRow("Distância da borda", self.margin)
        f3.addRow("Entrada", self.animation)
        f3.addRow("Palavra falada", self.highlight)
        f3.addRow("Cor do destaque", self.highlight_color)
        c3.body.addLayout(f3)
        form_l.addWidget(c3)
        form_l.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(ctrl)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(380)
        scroll.setMaximumWidth(430)
        root.addWidget(scroll)

        # ---- previa
        pv = Card("Prévia (renderizada como no vídeo final)")
        self.preview = QLabel("Gerando prévia…")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(320, 320)
        self.preview.setStyleSheet("background: #0b0c12; border-radius: 8px;")
        self.preview_note = hint("A prévia usa um quadro do primeiro vídeo da fila (ou um fundo de exemplo) "
                                 "e mostra o instante em que a 3ª palavra é falada.")
        pv.body.addWidget(self.preview, 1)
        pv.body.addWidget(self.preview_note)
        root.addWidget(pv, 1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(350)
        self._timer.timeout.connect(self._render)

        self.preset.currentTextChanged.connect(self._apply_preset)
        for w in (self.size, self.outline, self.shadow, self.glow, self.margin):
            w.valueChanged.connect(self._changed)
        for w in (self.words, self.box_opacity):
            w.valueChanged.connect(self._changed)
        for w in (self.bold, self.upper, self.box):
            w.toggled.connect(self._changed)
        for w in (self.position, self.animation, self.highlight):
            w.currentIndexChanged.connect(self._changed)
        self.font.currentTextChanged.connect(self._changed)
        for w in (self.color, self.outline_color, self.box_color, self.highlight_color):
            w.changed.connect(self._changed)

    # ------------------------------------------------------------------
    def style(self) -> SubtitleStyle:
        return SubtitleStyle(
            font=self.font.currentText().strip() or "Arial", size=self.size.value(), bold=self.bold.isChecked(),
            uppercase=self.upper.isChecked(), color=self.color.color(), outline_color=self.outline_color.color(),
            outline=self.outline.value(), shadow=self.shadow.value(), glow=self.glow.value(),
            box=self.box.isChecked(), box_color=self.box_color.color(), box_opacity=self.box_opacity.value() / 100,
            position=POSITIONS[self.position.currentIndex()][0], margin=self.margin.value(),
            animation=ANIMATIONS[self.animation.currentIndex()][0],
            highlight=HIGHLIGHTS[self.highlight.currentIndex()][0],
            highlight_color=self.highlight_color.color(), max_words=self.words.value(),
        )

    def set_style(self, s: SubtitleStyle) -> None:
        self._loading = True
        try:
            self.font.setCurrentText(s.font)
            self.size.setValue(s.size)
            self.bold.setChecked(s.bold)
            self.upper.setChecked(s.uppercase)
            self.color.set_color(s.color)
            self.outline_color.set_color(s.outline_color)
            self.outline.setValue(s.outline)
            self.shadow.setValue(s.shadow)
            self.glow.setValue(s.glow)
            self.box.setChecked(s.box)
            self.box_color.set_color(s.box_color)
            self.box_opacity.setValue(round(s.box_opacity * 100))
            self.position.setCurrentIndex([p for p, _ in POSITIONS].index(s.position))
            self.margin.setValue(s.margin)
            self.animation.setCurrentIndex([a for a, _ in ANIMATIONS].index(s.animation))
            self.highlight.setCurrentIndex([h for h, _ in HIGHLIGHTS].index(s.highlight))
            self.highlight_color.set_color(s.highlight_color)
            self.words.setValue(s.max_words)
            match = next((n for n, p in self.presets.items() if p == s), CUSTOM)
            self.preset.setCurrentText(match)
        finally:
            self._loading = False
        self._timer.start()

    def _apply_preset(self, name: str) -> None:
        if self._loading or name == CUSTOM:
            return
        self.set_style(self.presets[name].model_copy())

    def _changed(self, *_) -> None:
        if self._loading:
            return
        self._loading = True
        self.preset.setCurrentText(CUSTOM)
        self._loading = False
        self._timer.start()

    def refresh(self) -> None:
        self._timer.start()

    def _render(self) -> None:
        try:
            style = self.style()
        except Exception:  # noqa: BLE001 - cor digitada pela metade etc.
            return
        self._seq += 1
        seq = self._seq
        w, h = (540, 960) if self.vertical else (960, 540)
        out = self._tmp / f"p{seq}.png"
        bg = self.background
        run_task(lambda _p: render_style_preview(style, out, width=w, height=h, background=bg),
                 on_done=lambda p, seq=seq: self._show(p, seq),
                 on_error=lambda e: self.preview.setText(f"Não consegui gerar a prévia:\n{e}"))

    def _show(self, path: Path, seq: int) -> None:
        if seq != self._seq:  # chegou uma previa mais nova no meio do caminho
            return
        pix = QPixmap(str(path))
        box = self.preview.size()
        self.preview.setPixmap(pix.scaled(box.width() - 8, box.height() - 8, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))


class StylePage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")
        register_fonts()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 18)
        lay.setSpacing(10)
        lay.addWidget(page_header("Estilo das legendas",
                                  "Escolha um modelo pronto ou monte o seu: fonte, cores, contorno, caixa, posição, "
                                  "animação e destaque da palavra falada. A prévia é exatamente o que sai no vídeo."))
        self.tabs = QTabWidget()
        self.h = StyleEditor(PRESETS_H, vertical=False)
        self.v = StyleEditor(PRESETS_V, vertical=True)
        self.tabs.addTab(self.h, "Vídeo da aula (16:9)")
        self.tabs.addTab(self.v, "Cortes para redes (9:16)")
        lay.addWidget(self.tabs, 1)
        bar = QHBoxLayout()
        self.saved = QLabel()
        self.saved.setObjectName("muted")
        self.btn_save = QPushButton("Salvar estilos")
        self.btn_save.setObjectName("primary")
        bar.addWidget(self.saved)
        bar.addStretch(1)
        bar.addWidget(self.btn_save)
        lay.addLayout(bar)
        self.btn_save.clicked.connect(self.save)
        self.tabs.currentChanged.connect(lambda _i: self.tabs.currentWidget().refresh())
        base = state.load_base_settings()
        self.h.set_style(base.subtitles.style_h)
        self.v.set_style(base.subtitles.style_v)

    def set_background(self, video: Path | None) -> None:
        if video != self.h.background:
            self.h.background = self.v.background = video
            self.tabs.currentWidget().refresh()

    def save(self) -> None:
        try:
            s = state.compose(state.load_base_settings(), {"subtitles": {
                "style_h": self.h.style().model_dump(), "style_v": self.v.style().model_dump()}})
        except Exception as exc:  # noqa: BLE001
            self.saved.setText(f"Valor inválido: {exc}")
            return
        state.save_base_settings(s)
        self.saved.setText("Estilos salvos. Valem para os próximos processamentos.")
