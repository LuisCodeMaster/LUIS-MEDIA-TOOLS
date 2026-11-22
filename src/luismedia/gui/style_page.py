"""Estilo das legendas (estilo CapCut) com previa real renderizada pelo proprio libass.

- modelos prontos + modelos do usuario (salvar, excluir, exportar, importar)
- texto: fonte, tamanho, cor, duas cores alternadas, gradiente, maiusculas
- contorno, sombra, brilho neon, caixa de fundo
- posicao fixa ou livre (arrastando a legenda na previa)
- animacao de entrada: fade, pop, quicar, deslizar, maquina de escrever
- palavra falada: cor, cor + pop, caixa colorida (marca-texto), karaoke
- palavras-chave (IA + vocabulario) e emojis automaticos
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontDatabase, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
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
from .widgets import Card, hint, page_header, row

CUSTOM = "Personalizado"
USER_PREFIX = "★ "
POSITIONS = [("bottom", "Embaixo"), ("middle", "No meio"), ("top", "Em cima"),
             ("custom", "Livre (arraste na prévia)")]
ANIMATIONS = [("none", "Nenhuma"), ("fade", "Surgir suave (fade)"), ("pop", "Pop (cresce rápido)"),
              ("bounce", "Quicar (bounce)"), ("slide", "Deslizar de baixo"), ("typewriter", "Máquina de escrever")]
HIGHLIGHTS = [("none", "Sem destaque"), ("color", "Palavra falada colorida"),
              ("pop", "Palavra colorida + pop"), ("box", "Caixa colorida na palavra (marca-texto)"),
              ("reveal", "Revelar palavra por palavra (karaokê)")]


def register_fonts() -> None:
    for f in fonts_dir().glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(f))


# ---------------------------------------------------------------------- modelos do usuario
def _user_file() -> Path:
    return state.data_dir() / "estilos.json"


def load_user_presets() -> dict[str, dict[str, SubtitleStyle]]:
    out: dict[str, dict[str, SubtitleStyle]] = {"h": {}, "v": {}}
    try:
        raw = json.loads(_user_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    for kind in ("h", "v"):
        for name, data in (raw.get(kind) or {}).items():
            try:
                out[kind][name] = SubtitleStyle.model_validate(data)
            except Exception:  # noqa: BLE001 - modelo antigo/corrompido: ignora so ele
                continue
    return out


def save_user_presets(presets: dict[str, dict[str, SubtitleStyle]]) -> None:
    data = {k: {n: s.model_dump() for n, s in v.items()} for k, v in presets.items()}
    p = _user_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


# ---------------------------------------------------------------------- widgets
class ColorButton(QPushButton):
    changed = Signal(str)

    def __init__(self, color: str = "#FFFFFF") -> None:
        super().__init__()
        self.setFixedSize(46, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(lambda _c=False: self._pick())
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


class PreviewLabel(QLabel):
    """Mostra a previa e permite arrastar a legenda (posicao livre)."""

    moved = Signal(float, float, bool)  # x%, y%, terminou (soltou o mouse)

    def __init__(self) -> None:
        super().__init__("Gerando prévia…")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 320)
        self.setStyleSheet("background: #0b0c12; border-radius: 8px;")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Arraste para mudar a posição da legenda")
        self._src: QPixmap | None = None
        self._marker: QPointF | None = None
        self._dragging = False

    def set_image(self, pix: QPixmap) -> None:
        self._src = pix
        self._marker = None
        self._refit()

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self._refit()

    def _refit(self) -> None:
        if self._src is None or self._src.isNull():
            return
        self.setPixmap(self._src.scaled(max(1, self.width() - 8), max(1, self.height() - 8),
                                        Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation))

    def image_rect(self) -> QRectF | None:
        pix = self.pixmap()
        if pix is None or pix.isNull():
            return None
        return QRectF((self.width() - pix.width()) / 2, (self.height() - pix.height()) / 2,
                      pix.width(), pix.height())

    def drag_to(self, px: float, py: float, done: bool) -> None:
        r = self.image_rect()
        if r is None:
            return
        px = min(max(px, r.left()), r.right())
        py = min(max(py, r.top()), r.bottom())
        self._marker = QPointF(px, py)
        self.update()
        self.moved.emit(100 * (px - r.left()) / r.width(), 100 * (py - r.top()) / r.height(), done)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.drag_to(e.position().x(), e.position().y(), False)

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if self._dragging:
            self.drag_to(e.position().x(), e.position().y(), False)

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if self._dragging:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.drag_to(e.position().x(), e.position().y(), True)

    def paintEvent(self, e) -> None:  # noqa: N802
        super().paintEvent(e)
        if self._marker is not None:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QPen(QColor("#818cf8"), 2))
            m = self._marker
            p.drawEllipse(m, 10, 10)
            p.drawLine(QPointF(m.x() - 18, m.y()), QPointF(m.x() + 18, m.y()))
            p.drawLine(QPointF(m.x(), m.y() - 18), QPointF(m.x(), m.y() + 18))
            p.end()


def _spin(lo: float, hi: float, step: float = 0.5, suffix: str = "", decimals: int = 2) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setDecimals(decimals)
    if suffix:
        s.setSuffix(suffix)
    s.setFixedWidth(120)
    return s


class StyleEditor(QWidget):
    """Controles de um estilo + previa. Usado duas vezes: 16:9 (kind="h") e 9:16 (kind="v")."""

    def __init__(self, presets: dict[str, SubtitleStyle], vertical: bool) -> None:
        super().__init__()
        self.builtin, self.vertical = presets, vertical
        self.kind = "v" if vertical else "h"
        self._loading = False
        self.background: Path | None = None
        self._tmp = Path(tempfile.mkdtemp(prefix="lmt_preview_"))
        self._seq = 0

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 8, 0, 0)
        root.setSpacing(16)

        ctrl = QWidget()
        form_l = QVBoxLayout(ctrl)
        form_l.setContentsMargins(0, 0, 6, 0)
        form_l.setSpacing(12)

        # ---- modelo
        c0 = Card("Modelo")
        self.preset = QComboBox()
        c0.body.addWidget(self.preset)
        self.btn_save_as = QPushButton("Salvar como modelo…")
        self.btn_delete = QPushButton("Excluir")
        self.btn_export = QPushButton("Exportar…")
        self.btn_import = QPushButton("Importar…")
        c0.body.addWidget(row(self.btn_save_as, self.btn_delete))
        c0.body.addWidget(row(self.btn_export, self.btn_import))
        c0.body.addWidget(hint("Seus modelos aparecem com ★. Exporte para usar em outro computador "
                               "ou mandar para um cliente."))
        form_l.addWidget(c0)

        # ---- texto
        c1 = Card("Texto")
        f1 = QFormLayout()
        self.font = QComboBox()
        self.font.setEditable(True)
        self.font.addItems(BUNDLED_FONTS + SYSTEM_FONTS)
        self.size = _spin(2, 15, suffix=" %")
        self.bold = QCheckBox("Negrito")
        self.upper = QCheckBox("MAIÚSCULAS")
        self.color = ColorButton()
        self.alt = QCheckBox("Duas cores alternadas")
        self.color2 = ColorButton("#FFE600")
        self.gradient = QCheckBox("Gradiente")
        self.gradient_color = ColorButton("#FF7A00")
        self.words = QSpinBox()
        self.words.setRange(0, 12)
        self.words.setSpecialValueText("Automático")
        self.words.setFixedWidth(130)
        f1.addRow("Fonte", self.font)
        f1.addRow("Tamanho", self.size)
        f1.addRow("Cor do texto", self.color)
        f1.addRow("", self.bold)
        f1.addRow("", self.upper)
        f1.addRow(self.alt, self.color2)
        f1.addRow(self.gradient, self.gradient_color)
        f1.addRow("Palavras por legenda", self.words)
        c1.body.addLayout(f1)
        c1.body.addWidget(hint("Gradiente: da cor do texto (em cima) para a cor escolhida (embaixo). "
                               "Duas cores: alterna a cor entre as legendas."))
        form_l.addWidget(c1)

        # ---- contorno / caixa
        c2 = Card("Contorno, sombra e caixa")
        f2 = QFormLayout()
        self.outline_color = ColorButton("#000000")
        self.outline = _spin(0, 12)
        self.shadow = _spin(0, 10)
        self.glow = _spin(0, 10)
        self.box = QCheckBox("Caixa de fundo")
        self.box_color = ColorButton("#000000")
        self.box_opacity = QSpinBox()
        self.box_opacity.setRange(0, 100)
        self.box_opacity.setSuffix(" %")
        self.box_opacity.setFixedWidth(120)
        f2.addRow("Cor do contorno", self.outline_color)
        f2.addRow("Espessura do contorno", self.outline)
        f2.addRow("Sombra", self.shadow)
        f2.addRow("Brilho (neon)", self.glow)
        f2.addRow("", self.box)
        f2.addRow("Cor da caixa", self.box_color)
        f2.addRow("Opacidade da caixa", self.box_opacity)
        c2.body.addLayout(f2)
        form_l.addWidget(c2)

        # ---- posicao e animacao
        c3 = Card("Posição e animação")
        f3 = QFormLayout()
        self.position = QComboBox()
        for _, label in POSITIONS:
            self.position.addItem(label)
        self.margin = _spin(0, 45, 1, " %")
        self.pos_x = _spin(0, 100, 1, " %", 1)
        self.pos_y = _spin(0, 100, 1, " %", 1)
        self.animation = QComboBox()
        for _, label in ANIMATIONS:
            self.animation.addItem(label)
        self.highlight = QComboBox()
        for _, label in HIGHLIGHTS:
            self.highlight.addItem(label)
        self.highlight_color = ColorButton("#FFE600")
        f3.addRow("Posição", self.position)
        f3.addRow("Distância da borda", self.margin)
        f3.addRow("Horizontal (livre)", self.pos_x)
        f3.addRow("Vertical (livre)", self.pos_y)
        f3.addRow("Entrada", self.animation)
        f3.addRow("Palavra falada", self.highlight)
        f3.addRow("Cor do destaque", self.highlight_color)
        c3.body.addLayout(f3)
        form_l.addWidget(c3)

        # ---- destaques automaticos
        c4 = Card("Destaques automáticos")
        f4 = QFormLayout()
        self.keywords = QCheckBox("Destacar palavras-chave")
        self.keyword_color = ColorButton("#22D3EE")
        self.keyword_scale = _spin(100, 160, 5, " %", 0)
        self.emojis = QCheckBox("Emojis automáticos")
        self.emoji_size = _spin(4, 20, 0.5, " %")
        f4.addRow(self.keywords, self.keyword_color)
        f4.addRow("Tamanho da palavra-chave", self.keyword_scale)
        f4.addRow("", self.emojis)
        f4.addRow("Tamanho do emoji", self.emoji_size)
        c4.body.addLayout(f4)
        c4.body.addWidget(hint("As palavras-chave são escolhidas pela IA (com o Ollama aberto) e somadas ao "
                               "vocabulário da aula; dá para editar em Revisar legendas. Os emojis aparecem acima "
                               "da legenda quando ela fala de dinheiro, ideia, tempo, estudo, erro, acerto etc."))
        form_l.addWidget(c4)
        form_l.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(ctrl)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(400)
        scroll.setMaximumWidth(460)
        root.addWidget(scroll)

        # ---- previa
        pv = Card("Prévia (renderizada como no vídeo final)")
        self.preview = PreviewLabel()
        self.preview_note = hint("Quadro do primeiro vídeo da fila (ou um fundo de exemplo) no instante em que a "
                                 "2ª palavra é falada. Arraste na prévia para colocar a legenda onde quiser.")
        pv.body.addWidget(self.preview, 1)
        pv.body.addWidget(self.preview_note)
        root.addWidget(pv, 1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(350)
        self._timer.timeout.connect(self._render)

        self.preset.currentTextChanged.connect(self._apply_preset)
        for w in (self.size, self.outline, self.shadow, self.glow, self.margin, self.pos_x, self.pos_y,
                  self.keyword_scale, self.emoji_size, self.words, self.box_opacity):
            w.valueChanged.connect(self._changed)
        for w in (self.bold, self.upper, self.box, self.alt, self.gradient, self.keywords, self.emojis):
            w.toggled.connect(self._changed)
        for w in (self.position, self.animation, self.highlight):
            w.currentIndexChanged.connect(self._changed)
        self.font.currentTextChanged.connect(self._changed)
        for w in (self.color, self.color2, self.gradient_color, self.outline_color, self.box_color,
                  self.highlight_color, self.keyword_color):
            w.changed.connect(self._changed)
        self.preview.moved.connect(self._dragged)
        self.btn_save_as.clicked.connect(lambda _c=False: self._save_as())
        self.btn_delete.clicked.connect(lambda _c=False: self._delete_user())
        self.btn_export.clicked.connect(lambda _c=False: self._export())
        self.btn_import.clicked.connect(lambda _c=False: self._import())
        self._reload_presets(CUSTOM)

    # ------------------------------------------------------------------ modelos
    def all_presets(self) -> dict[str, SubtitleStyle]:
        user = load_user_presets()[self.kind]
        return {**self.builtin, **{USER_PREFIX + n: s for n, s in user.items()}}

    def _reload_presets(self, select: str | None = None) -> None:
        self._loading = True
        current = select or self.preset.currentText()
        self.preset.clear()
        self.preset.addItems([*self.all_presets().keys(), CUSTOM])
        self.preset.setCurrentText(current if self.preset.findText(current) >= 0 else CUSTOM)
        self._loading = False
        self._sync()

    def save_user_preset(self, name: str) -> None:
        presets = load_user_presets()
        presets[self.kind][name] = self.style()
        save_user_presets(presets)
        self._reload_presets(USER_PREFIX + name)

    def delete_user_preset(self, name: str) -> None:
        presets = load_user_presets()
        presets[self.kind].pop(name, None)
        save_user_presets(presets)
        self._reload_presets(CUSTOM)

    def export_style(self, path: Path, name: str) -> None:
        path.write_text(json.dumps({"name": name, "kind": self.kind, "style": self.style().model_dump()},
                                   indent=2, ensure_ascii=False), encoding="utf-8")

    def import_style(self, path: Path) -> str:
        data = json.loads(path.read_text(encoding="utf-8"))
        style = SubtitleStyle.model_validate(data.get("style", data))
        name = str(data.get("name") or path.stem.replace(".estilo", "")).strip() or "Importado"
        presets = load_user_presets()
        presets[self.kind][name] = style
        save_user_presets(presets)
        self._reload_presets()
        self.set_style(style)
        return name

    def _save_as(self) -> None:
        try:
            self.style()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Estilo inválido", str(exc))
            return
        cur = self.preset.currentText()
        default = cur[len(USER_PREFIX):] if cur.startswith(USER_PREFIX) else ""
        name, ok = QInputDialog.getText(self, "Salvar modelo", "Nome do modelo:", text=default)
        if ok and name.strip():
            self.save_user_preset(name.strip())

    def _delete_user(self) -> None:
        cur = self.preset.currentText()
        if not cur.startswith(USER_PREFIX):
            return
        name = cur[len(USER_PREFIX):]
        if QMessageBox.question(self, "Excluir modelo", f"Excluir o modelo \"{name}\"?") \
                == QMessageBox.StandardButton.Yes:
            self.delete_user_preset(name)

    def _export(self) -> None:
        cur = self.preset.currentText().replace(USER_PREFIX, "")
        name = cur if cur != CUSTOM else "meu-estilo"
        f, _ = QFileDialog.getSaveFileName(self, "Exportar estilo", f"{name}.estilo.json", "Estilo (*.json)")
        if f:
            self.export_style(Path(f), name)

    def _import(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "Importar estilo", "", "Estilo (*.json)")
        if not f:
            return
        try:
            self.import_style(Path(f))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Arquivo inválido", f"Não consegui ler esse estilo:\n{exc}")

    # ------------------------------------------------------------------ valores
    def style(self) -> SubtitleStyle:
        return SubtitleStyle(
            font=self.font.currentText().strip() or "Arial", size=self.size.value(), bold=self.bold.isChecked(),
            uppercase=self.upper.isChecked(), color=self.color.color(), alt_colors=self.alt.isChecked(),
            color2=self.color2.color(), gradient=self.gradient.isChecked(),
            gradient_color=self.gradient_color.color(), outline_color=self.outline_color.color(),
            outline=self.outline.value(), shadow=self.shadow.value(), glow=self.glow.value(),
            box=self.box.isChecked(), box_color=self.box_color.color(), box_opacity=self.box_opacity.value() / 100,
            position=POSITIONS[self.position.currentIndex()][0], margin=self.margin.value(),
            pos_x=self.pos_x.value(), pos_y=self.pos_y.value(),
            animation=ANIMATIONS[self.animation.currentIndex()][0],
            highlight=HIGHLIGHTS[self.highlight.currentIndex()][0],
            highlight_color=self.highlight_color.color(), max_words=self.words.value(),
            keywords=self.keywords.isChecked(), keyword_color=self.keyword_color.color(),
            keyword_scale=self.keyword_scale.value(), emojis=self.emojis.isChecked(),
            emoji_size=self.emoji_size.value(),
        )

    def set_style(self, s: SubtitleStyle) -> None:
        self._loading = True
        try:
            self.font.setCurrentText(s.font)
            self.size.setValue(s.size)
            self.bold.setChecked(s.bold)
            self.upper.setChecked(s.uppercase)
            self.color.set_color(s.color)
            self.alt.setChecked(s.alt_colors)
            self.color2.set_color(s.color2)
            self.gradient.setChecked(s.gradient)
            self.gradient_color.set_color(s.gradient_color)
            self.outline_color.set_color(s.outline_color)
            self.outline.setValue(s.outline)
            self.shadow.setValue(s.shadow)
            self.glow.setValue(s.glow)
            self.box.setChecked(s.box)
            self.box_color.set_color(s.box_color)
            self.box_opacity.setValue(round(s.box_opacity * 100))
            self.position.setCurrentIndex([p for p, _ in POSITIONS].index(s.position))
            self.margin.setValue(s.margin)
            self.pos_x.setValue(s.pos_x)
            self.pos_y.setValue(s.pos_y)
            self.animation.setCurrentIndex([a for a, _ in ANIMATIONS].index(s.animation))
            self.highlight.setCurrentIndex([h for h, _ in HIGHLIGHTS].index(s.highlight))
            self.highlight_color.set_color(s.highlight_color)
            self.words.setValue(s.max_words)
            self.keywords.setChecked(s.keywords)
            self.keyword_color.set_color(s.keyword_color)
            self.keyword_scale.setValue(s.keyword_scale)
            self.emojis.setChecked(s.emojis)
            self.emoji_size.setValue(s.emoji_size)
            match = next((n for n, p in self.all_presets().items() if p == s), CUSTOM)
            self.preset.setCurrentText(match)
        finally:
            self._loading = False
        self._sync()
        self._timer.start()

    def _sync(self) -> None:
        """Habilita so os campos que fazem sentido para as opcoes escolhidas."""
        pos = POSITIONS[self.position.currentIndex()][0] if self.position.currentIndex() >= 0 else "bottom"
        self.margin.setEnabled(pos in ("bottom", "top"))
        self.pos_x.setEnabled(pos == "custom")
        self.pos_y.setEnabled(pos == "custom")
        self.color2.setEnabled(self.alt.isChecked())
        self.gradient_color.setEnabled(self.gradient.isChecked())
        self.box_color.setEnabled(self.box.isChecked())
        self.box_opacity.setEnabled(self.box.isChecked())
        hl = HIGHLIGHTS[self.highlight.currentIndex()][0] if self.highlight.currentIndex() >= 0 else "none"
        self.highlight_color.setEnabled(hl in ("color", "pop", "box"))
        self.keyword_color.setEnabled(self.keywords.isChecked())
        self.keyword_scale.setEnabled(self.keywords.isChecked())
        self.emoji_size.setEnabled(self.emojis.isChecked())
        self.btn_delete.setEnabled(self.preset.currentText().startswith(USER_PREFIX))

    def _apply_preset(self, name: str) -> None:
        if self._loading:
            return
        self._sync()
        p = self.all_presets().get(name)
        if p is not None:
            self.set_style(p.model_copy())

    def _changed(self, *_) -> None:
        if self._loading:
            return
        self._loading = True
        self.preset.setCurrentText(CUSTOM)
        self._loading = False
        self._sync()
        self._timer.start()

    def _dragged(self, x: float, y: float, done: bool) -> None:
        self._loading = True
        self.position.setCurrentIndex([p for p, _ in POSITIONS].index("custom"))
        self.pos_x.setValue(round(x, 1))
        self.pos_y.setValue(round(y, 1))
        self.preset.setCurrentText(CUSTOM)
        self._loading = False
        self._sync()
        if done:
            self._render()

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
        self.preview.set_image(QPixmap(str(path)))


class StylePage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")
        register_fonts()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 18)
        lay.setSpacing(10)
        lay.addWidget(page_header("Estilo das legendas",
                                  "Legendas no estilo CapCut: fontes, cores, gradiente, caixa na palavra falada, "
                                  "animações, palavras-chave e emojis. A prévia é exatamente o que sai no vídeo."))
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
        self.btn_save.clicked.connect(lambda _c=False: self.save())
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
