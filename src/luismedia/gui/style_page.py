"""Estilo das legendas: inspetor compacto (estilo editor de video) + monitor com player.

Layout:
    [ Modelo ▾ ] [ Salvar modelo ] [ ⋯ ]                     (barra do modelo)
    | Texto | Cores | Caixa | Posição | Animação | Extras |  monitor (previa real)
    | campos da secao escolhida                           |  ▶  ━━━━━●━━━━━  00:12 / 05:40

A previa e desenhada pelo mesmo motor do video final (libass + FFmpeg): um quadro parado
quando pausado e um trecho animado de 4 s quando em reproducao, no momento escolhido na
linha do tempo, com as legendas reais do video quando ele ja foi revisado.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFontDatabase, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core.models import Segment
from ..core.style import BUNDLED_FONTS, PRESETS_H, PRESETS_V, SYSTEM_FONTS, SubtitleStyle, fonts_dir
from ..stages.media import (
    PREVIEW_CLIP_SECONDS,
    PREVIEW_FPS,
    render_style_clip,
    render_style_preview,
)
from . import state
from .tasks import run_task

CUSTOM = "Personalizado"
USER_PREFIX = "★ "
POSITIONS = [("bottom", "Embaixo"), ("middle", "No meio"), ("top", "Em cima"),
             ("custom", "Livre (arraste na prévia)")]
ANIMATIONS = [("none", "Nenhuma"), ("fade", "Surgir suave"), ("pop", "Pop"),
              ("bounce", "Quicar"), ("slide", "Deslizar de baixo"), ("typewriter", "Máquina de escrever")]
HIGHLIGHTS = [("none", "Sem destaque"), ("color", "Cor"), ("pop", "Cor + pop"),
              ("box", "Caixa colorida (marca-texto)"), ("reveal", "Revelar palavra por palavra")]
SECTIONS = ["Texto", "Cores", "Caixa", "Posição", "Animação", "Extras"]


def register_fonts() -> None:
    for f in fonts_dir().glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(f))


def fmt_time(sec: float) -> str:
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    return f"{h}:{rem // 60:02d}:{rem % 60:02d}" if h else f"{rem // 60:02d}:{rem % 60:02d}"


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


# ---------------------------------------------------------------------- fonte da previa
@dataclass
class PreviewSource:
    """De onde vem a previa: video da fila (ou nenhum) e, se ja revisado, as legendas reais."""

    video: Path | None = None
    duration: float = 0.0
    segments: list[Segment] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.video}|{self.duration}|{len(self.segments)}|{','.join(self.keywords)}"


# ---------------------------------------------------------------------- widgets
class ColorButton(QPushButton):
    changed = Signal(str)

    def __init__(self, color: str = "#FFFFFF") -> None:
        super().__init__()
        self.setObjectName("swatch")
        self.setFixedSize(40, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(lambda _c=False: self._pick())
        self.set_color(color)

    def set_color(self, color: str) -> None:
        self._color = color.upper()
        self.setStyleSheet(f"QPushButton#swatch {{ background: {self._color}; }}")
        self.setToolTip(self._color)

    def color(self) -> str:
        return self._color

    def _pick(self) -> None:
        c = QColorDialog.getColor(QColor(self._color), self, "Escolher cor")
        if c.isValid():
            self.set_color(c.name())
            self.changed.emit(self._color)


class PreviewLabel(QLabel):
    """Monitor: mostra a previa e permite arrastar a legenda (posicao livre)."""

    moved = Signal(float, float, bool)  # x%, y%, terminou (soltou o mouse)
    pressed = Signal()

    def __init__(self) -> None:
        super().__init__("Gerando prévia…")
        self.setObjectName("monitor")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Arraste para posicionar a legenda")
        self._src: QPixmap | None = None
        self._marker: QPointF | None = None
        self._dragging = False

    def set_image(self, pix: QPixmap, keep_marker: bool = False) -> None:
        self._src = pix
        if not keep_marker:
            self._marker = None
        self._refit()

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self._refit()

    def _refit(self) -> None:
        if self._src is None or self._src.isNull():
            return
        self.setPixmap(self._src.scaled(max(1, self.width() - 4), max(1, self.height() - 4),
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
            self.pressed.emit()
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
            p.setPen(QPen(QColor("#818cf8"), 1.5))
            m = self._marker
            p.drawEllipse(m, 9, 9)
            p.drawLine(QPointF(m.x() - 16, m.y()), QPointF(m.x() + 16, m.y()))
            p.drawLine(QPointF(m.x(), m.y() - 16), QPointF(m.x(), m.y() + 16))
            p.end()


def _spin(lo: float, hi: float, step: float = 0.5, suffix: str = "", decimals: int = 1) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setDecimals(decimals)
    if suffix:
        s.setSuffix(suffix)
    s.setFixedWidth(110)
    return s


def _combo(items: list[tuple[str, str]]) -> QComboBox:
    c = QComboBox()
    for _, label in items:
        c.addItem(label)
    return c


def _form() -> tuple[QWidget, QFormLayout]:
    w = QWidget()
    f = QFormLayout(w)
    f.setContentsMargins(2, 14, 2, 4)
    f.setHorizontalSpacing(16)
    f.setVerticalSpacing(12)
    f.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    return w, f


def _pair(*widgets: QWidget) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)
    for x in widgets:
        lay.addWidget(x)
    lay.addStretch(1)
    return w


class StyleEditor(QWidget):
    """Inspetor de um estilo + monitor. Usado duas vezes: 16:9 (kind="h") e 9:16 (kind="v")."""

    edited = Signal()  # o usuario mudou algo no estilo

    def __init__(self, presets: dict[str, SubtitleStyle], vertical: bool) -> None:
        super().__init__()
        self.builtin, self.vertical = presets, vertical
        self.kind = "v" if vertical else "h"
        self._loading = False
        self.source = PreviewSource()
        self._tmp = Path(tempfile.mkdtemp(prefix="lmt_preview_"))
        self._seq = 0
        self._moment = 0.0                  # segundo do video mostrado na previa
        self._frames: list[Path] = []       # trecho animado pronto
        self._frames_key = ""
        self._frame_i = 0
        self._playing = False

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 10, 0, 0)
        root.setSpacing(18)
        root.addWidget(self._build_inspector())
        root.addWidget(self._build_monitor(), 1)

        self._timer = QTimer(self)          # debounce: espera o usuario parar de mexer
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._render)
        self._play_timer = QTimer(self)
        self._play_timer.setInterval(round(1000 / PREVIEW_FPS))
        self._play_timer.timeout.connect(self._tick)

        self._connect()
        self._reload_presets(CUSTOM)
        self._update_timeline()

    # ------------------------------------------------------------------ montagem
    def _build_inspector(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("inspector")
        panel.setFixedWidth(430)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        # ---- modelo
        cap = QLabel("MODELO")
        cap.setObjectName("caption")
        lay.addWidget(cap)
        self.preset = QComboBox()
        self.btn_save_as = QPushButton("Salvar")
        self.btn_save_as.setToolTip("Salvar o estilo atual como um modelo seu")
        self.btn_more = QToolButton()
        self.btn_more.setObjectName("more")
        self.btn_more.setText("⋯")
        self.btn_more.setToolTip("Mais opções")
        self.btn_more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.btn_more)
        self.act_export = QAction("Exportar estilo…", self)
        self.act_import = QAction("Importar estilo…", self)
        self.act_delete = QAction("Excluir modelo", self)
        menu.addAction(self.act_export)
        menu.addAction(self.act_import)
        menu.addSeparator()
        menu.addAction(self.act_delete)
        self.btn_more.setMenu(menu)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(self.preset, 1)
        top.addWidget(self.btn_save_as)
        top.addWidget(self.btn_more)
        lay.addLayout(top)

        line = QFrame()
        line.setObjectName("divider")
        line.setFixedHeight(1)
        lay.addWidget(line)

        # ---- secoes
        seg = QHBoxLayout()
        seg.setSpacing(2)
        self.sections = QButtonGroup(self)
        self.sections.setExclusive(True)
        for i, name in enumerate(SECTIONS):
            b = QPushButton(name)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.sections.addButton(b, i)
            seg.addWidget(b)
        seg.addStretch(1)
        lay.addLayout(seg)
        self.pages = QStackedWidget()
        for build in (self._page_text, self._page_colors, self._page_box, self._page_position,
                      self._page_animation, self._page_extras):
            self.pages.addWidget(build())
        lay.addWidget(self.pages)
        lay.addStretch(1)
        self.sections.button(0).setChecked(True)
        self.sections.idClicked.connect(self.pages.setCurrentIndex)
        return panel

    def _page_text(self) -> QWidget:
        w, f = _form()
        self.font = QComboBox()
        self.font.setEditable(True)
        self.font.addItems(BUNDLED_FONTS + SYSTEM_FONTS)
        self.size = _spin(2, 15, 0.5, " %")
        self.size.setToolTip("Altura da letra em % do lado menor do vídeo")
        self.bold = QCheckBox("Negrito")
        self.upper = QCheckBox("MAIÚSCULAS")
        self.words = QSpinBox()
        self.words.setRange(0, 12)
        self.words.setSpecialValueText("Automático")
        self.words.setFixedWidth(130)
        self.words.setToolTip("Quantas palavras aparecem por vez (Automático = pelo tamanho da linha)")
        f.addRow("Fonte", self.font)
        f.addRow("Tamanho", self.size)
        f.addRow("", _pair(self.bold, self.upper))
        f.addRow("Palavras por vez", self.words)
        return w

    def _page_colors(self) -> QWidget:
        w, f = _form()
        self.color = ColorButton()
        self.alt = QCheckBox("Alternar")
        self.alt.setToolTip("Alterna entre a cor do texto e esta cor a cada legenda")
        self.color2 = ColorButton("#FFE600")
        self.gradient = QCheckBox("Ativar")
        self.gradient.setToolTip("Degradê de cima (cor do texto) para baixo (esta cor)")
        self.gradient_color = ColorButton("#FF7A00")
        self.outline_color = ColorButton("#000000")
        self.outline = _spin(0, 12, 0.5)
        self.shadow = _spin(0, 10, 0.5)
        self.glow = _spin(0, 10, 0.5)
        self.glow.setToolTip("Desfoca o contorno para um efeito neon")
        f.addRow("Texto", self.color)
        f.addRow("Duas cores", _pair(self.alt, self.color2))
        f.addRow("Gradiente", _pair(self.gradient, self.gradient_color))
        f.addRow("Contorno", _pair(self.outline_color, self.outline))
        f.addRow("Sombra", self.shadow)
        f.addRow("Brilho neon", self.glow)
        return w

    def _page_box(self) -> QWidget:
        w, f = _form()
        self.box = QCheckBox("Caixa atrás do texto")
        self.box_color = ColorButton("#000000")
        self.box_opacity = QSpinBox()
        self.box_opacity.setRange(0, 100)
        self.box_opacity.setSuffix(" %")
        self.box_opacity.setFixedWidth(110)
        f.addRow("", self.box)
        f.addRow("Cor", self.box_color)
        f.addRow("Opacidade", self.box_opacity)
        self._box_form = f
        return w

    def _page_position(self) -> QWidget:
        w, f = _form()
        self.position = _combo(POSITIONS)
        self.margin = _spin(0, 45, 1, " %")
        self.margin.setToolTip("Distância da borda, em % da altura")
        self.pos_x = _spin(0, 100, 1, " %")
        self.pos_y = _spin(0, 100, 1, " %")
        f.addRow("Posição", self.position)
        f.addRow("Margem", self.margin)
        f.addRow("Horizontal", self.pos_x)
        f.addRow("Vertical", self.pos_y)
        self._pos_form = f
        return w

    def _page_animation(self) -> QWidget:
        w, f = _form()
        self.animation = _combo(ANIMATIONS)
        self.highlight = _combo(HIGHLIGHTS)
        self.highlight_color = ColorButton("#FFE600")
        f.addRow("Entrada", self.animation)
        f.addRow("Palavra falada", self.highlight)
        f.addRow("Cor do destaque", self.highlight_color)
        self._anim_form = f
        return w

    def _page_extras(self) -> QWidget:
        w, f = _form()
        self.keywords = QCheckBox("Ativar")
        self.keywords.setToolTip("A IA escolhe os termos importantes da aula (edite em Revisar legendas)")
        self.keyword_color = ColorButton("#22D3EE")
        self.keyword_scale = _spin(100, 160, 5, " %", 0)
        self.emojis = QCheckBox("Ativar")
        self.emojis.setToolTip("Emoji acima da legenda quando ela fala de dinheiro, ideia, tempo, estudo…")
        self.emoji_size = _spin(4, 20, 0.5, " %")
        f.addRow("Palavras-chave", _pair(self.keywords, self.keyword_color))
        f.addRow("Tamanho", self.keyword_scale)
        f.addRow("Emojis", self.emojis)
        f.addRow("Tamanho do emoji", self.emoji_size)
        self._extras_form = f
        return w

    def _build_monitor(self) -> QWidget:
        w = QFrame()
        w.setObjectName("stage")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 10)
        lay.setSpacing(10)
        self.preview = PreviewLabel()
        lay.addWidget(self.preview, 1)

        self.btn_play = QPushButton("▶")
        self.btn_play.setObjectName("play")
        self.btn_play.setFixedSize(38, 38)
        self.btn_play.setToolTip("Reproduzir a prévia (4 s a partir do ponto escolhido)")
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.setObjectName("timeline")
        self.timeline.setToolTip("Escolha o momento do vídeo para a prévia")
        self.time_lbl = QLabel("00:00 / 00:00")
        self.time_lbl.setObjectName("timecode")
        bar = QHBoxLayout()
        bar.setSpacing(12)
        bar.addWidget(self.btn_play)
        bar.addWidget(self.timeline, 1)
        bar.addWidget(self.time_lbl)
        lay.addLayout(bar)
        self.source_lbl = QLabel()
        self.source_lbl.setObjectName("hint")
        lay.addWidget(self.source_lbl)
        return w

    def _connect(self) -> None:
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
        self.preview.pressed.connect(self.pause)
        self.btn_save_as.clicked.connect(lambda _c=False: self._save_as())
        self.act_delete.triggered.connect(lambda _c=False: self._delete_user())
        self.act_export.triggered.connect(lambda _c=False: self._export())
        self.act_import.triggered.connect(lambda _c=False: self._import())
        self.btn_play.clicked.connect(lambda _c=False: self.toggle_play())
        self.timeline.valueChanged.connect(self._timeline_moved)
        self.timeline.sliderReleased.connect(self._timeline_released)

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
        self._style_changed()

    def _sync(self) -> None:
        """Mostra so os campos que fazem sentido para as opcoes escolhidas."""
        pos = POSITIONS[max(0, self.position.currentIndex())][0]
        self.margin.setEnabled(pos in ("bottom", "top"))
        self.pos_x.setEnabled(pos == "custom")
        self.pos_y.setEnabled(pos == "custom")
        self._pos_form.setRowVisible(self.margin, pos in ("bottom", "top"))
        self._pos_form.setRowVisible(self.pos_x, pos == "custom")
        self._pos_form.setRowVisible(self.pos_y, pos == "custom")
        for toggle_, swatch in ((self.alt, self.color2), (self.gradient, self.gradient_color),
                                (self.keywords, self.keyword_color)):
            swatch.setEnabled(toggle_.isChecked())
            swatch.setVisible(toggle_.isChecked())
        for w in (self.box_color, self.box_opacity):
            w.setEnabled(self.box.isChecked())
            self._box_form.setRowVisible(w, self.box.isChecked())
        hl = HIGHLIGHTS[max(0, self.highlight.currentIndex())][0]
        self.highlight_color.setEnabled(hl in ("color", "pop", "box"))
        self._anim_form.setRowVisible(self.highlight_color, hl in ("color", "pop", "box"))
        self.keyword_scale.setEnabled(self.keywords.isChecked())
        self._extras_form.setRowVisible(self.keyword_scale, self.keywords.isChecked())
        self.emoji_size.setEnabled(self.emojis.isChecked())
        self._extras_form.setRowVisible(self.emoji_size, self.emojis.isChecked())
        self.act_delete.setEnabled(self.preset.currentText().startswith(USER_PREFIX))

    def _apply_preset(self, name: str) -> None:
        if self._loading:
            return
        self._sync()
        p = self.all_presets().get(name)
        if p is not None:
            self.set_style(p.model_copy())
            self.edited.emit()

    def _changed(self, *_) -> None:
        if self._loading:
            return
        self._loading = True
        self.preset.setCurrentText(CUSTOM)
        self._loading = False
        self._sync()
        self.edited.emit()
        self._style_changed()

    def _dragged(self, x: float, y: float, done: bool) -> None:
        self._loading = True
        self.position.setCurrentIndex([p for p, _ in POSITIONS].index("custom"))
        self.pos_x.setValue(round(x, 1))
        self.pos_y.setValue(round(y, 1))
        self.preset.setCurrentText(CUSTOM)
        self._loading = False
        self._sync()
        if done:
            self.edited.emit()
            self._style_changed(now=True)

    # ------------------------------------------------------------------ fonte e linha do tempo
    def set_source(self, source: PreviewSource) -> None:
        if source.key == self.source.key:
            return
        self.source = source
        self._frames_key = ""
        if not source.video:
            self._moment = 0.0
        elif source.segments and not any(s.start <= self._moment < s.end for s in source.segments):
            self._moment = source.segments[0].start  # comeca na primeira fala
        self._moment = min(self._moment, max(0.0, source.duration - 0.5))
        self._update_timeline()
        self._style_changed()

    def _update_timeline(self) -> None:
        has_video = bool(self.source.video and self.source.duration > 0)
        self.timeline.blockSignals(True)
        self.timeline.setRange(0, round(self.source.duration * 1000) if has_video else 0)
        self.timeline.setValue(round(self._moment * 1000))
        self.timeline.blockSignals(False)
        self.timeline.setEnabled(has_video)
        self._show_time(self._moment)
        if not has_video:
            self.source_lbl.setText("Fundo de exemplo com frase de exemplo. Adicione um vídeo na fila para "
                                    "ver a legenda sobre ele.")
        elif self.source.segments:
            self.source_lbl.setText(f"Legendas reais de {self.source.video.name}.")
        else:
            self.source_lbl.setText(f"{self.source.video.name} com frase de exemplo (as legendas reais "
                                    "aparecem depois da transcrição, ao abrir em Revisar legendas).")

    def _show_time(self, t: float) -> None:
        total = self.source.duration if self.source.video else PREVIEW_CLIP_SECONDS
        self.time_lbl.setText(f"{fmt_time(t)} / {fmt_time(total)}")

    def _timeline_moved(self, ms: int) -> None:
        self._show_time(ms / 1000)
        if not self.timeline.isSliderDown():  # clique na barra / teclado
            self._timeline_released()

    def _timeline_released(self) -> None:
        self._moment = self.timeline.value() / 1000
        self._frames_key = ""
        self._style_changed(now=not self._playing)

    # ------------------------------------------------------------------ reproducao
    def _clip_key(self, style: SubtitleStyle) -> str:
        raw = f"{style.model_dump_json()}|{self.source.key}|{self._moment:.2f}"
        return hashlib.md5(raw.encode()).hexdigest()  # noqa: S324 - so chave de cache

    def toggle_play(self) -> None:
        if self._playing:
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        self._playing = True
        self.btn_play.setText("❚❚")
        try:
            key = self._clip_key(self.style())
        except Exception:  # noqa: BLE001
            return
        if key == self._frames_key and self._frames:
            self._frame_i = 0
            self._play_timer.start()
        else:
            self._render_clip()

    def pause(self) -> None:
        if not self._playing:
            return
        self._playing = False
        self._play_timer.stop()
        self.btn_play.setText("▶")
        self._update_timeline()

    @property
    def playing(self) -> bool:
        return self._playing

    def _tick(self) -> None:
        if not self._frames:
            return
        if self._frame_i >= len(self._frames):
            self._frame_i = 0  # repete o trecho, como um editor em loop
        self.preview.set_image(QPixmap(str(self._frames[self._frame_i])), keep_marker=False)
        t = self._moment + self._frame_i / PREVIEW_FPS
        self._show_time(t)
        if self.timeline.isEnabled() and not self.timeline.isSliderDown():
            self.timeline.blockSignals(True)
            self.timeline.setValue(round(t * 1000))
            self.timeline.blockSignals(False)
        self._frame_i += 1

    def _render_clip(self) -> None:
        try:
            style = self.style()
        except Exception:  # noqa: BLE001
            return
        self._seq += 1
        seq, key, src = self._seq, self._clip_key(style), self.source
        w, h = (540, 960) if self.vertical else (960, 540)
        out = self._tmp / f"clip{seq}"
        moment = self._moment
        self.btn_play.setEnabled(False)
        self.btn_play.setToolTip("Preparando a prévia…")
        run_task(lambda _p: render_style_clip(style, out, width=w, height=h, background=src.video, start=moment,
                                              segments=src.segments or None,
                                              keywords=src.keywords if src.segments else None),
                 on_done=lambda frames, seq=seq, key=key: self._clip_ready(frames, seq, key),
                 on_error=self._preview_failed)

    def _clip_ready(self, frames: list[Path], seq: int, key: str) -> None:
        self.btn_play.setEnabled(True)
        self.btn_play.setToolTip("Reproduzir / pausar a prévia")
        if seq != self._seq or not self._playing:
            return
        self._frames, self._frames_key, self._frame_i = frames, key, 0
        self._play_timer.start()

    # ------------------------------------------------------------------ previa parada
    def _style_changed(self, now: bool = False) -> None:
        if self._playing:
            self._play_timer.stop()
            self._timer.start()  # refaz o trecho animado quando o usuario parar de mexer
        elif now:
            self._render()
        else:
            self._timer.start()

    def refresh(self) -> None:
        self._timer.start()

    def _render(self) -> None:
        if self._playing:
            self._render_clip()
            return
        try:
            style = self.style()
        except Exception:  # noqa: BLE001 - cor digitada pela metade etc.
            return
        self._seq += 1
        seq, src, moment = self._seq, self.source, self._moment
        w, h = (540, 960) if self.vertical else (960, 540)
        out = self._tmp / f"p{seq}.png"
        run_task(lambda _p: render_style_preview(style, out, width=w, height=h, background=src.video,
                                                 start=moment if src.video else 1.0,
                                                 segments=src.segments or None,
                                                 keywords=src.keywords if src.segments else None),
                 on_done=lambda p, seq=seq: self._show(p, seq),
                 on_error=self._preview_failed)

    def _preview_failed(self, err: str) -> None:
        self.btn_play.setEnabled(True)
        self.preview.setText(f"Não consegui gerar a prévia:\n{err}")

    def _show(self, path: Path, seq: int) -> None:
        if seq != self._seq or self._playing:  # chegou uma previa mais nova no meio do caminho
            return
        self.preview.set_image(QPixmap(str(path)), keep_marker=True)


class StylePage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")
        register_fonts()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 18)
        lay.setSpacing(6)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        t = QLabel("Estilo das legendas")
        t.setObjectName("pageTitle")
        sub = QLabel("A prévia usa o mesmo motor que gera o vídeo final.")
        sub.setObjectName("pageSubtitle")
        titles.addWidget(t)
        titles.addWidget(sub)
        head.addLayout(titles)
        head.addStretch(1)
        self.saved = QLabel()
        self.saved.setObjectName("muted")
        self.btn_save = QPushButton("Salvar estilos")
        self.btn_save.setObjectName("primary")
        head.addWidget(self.saved)
        head.addSpacing(10)
        head.addWidget(self.btn_save)
        lay.addLayout(head)

        self.tabs = QTabWidget()
        self.h = StyleEditor(PRESETS_H, vertical=False)
        self.v = StyleEditor(PRESETS_V, vertical=True)
        self.tabs.addTab(self.h, "Aula 16:9")
        self.tabs.addTab(self.v, "Cortes 9:16")
        lay.addWidget(self.tabs, 1)
        self.btn_save.clicked.connect(lambda _c=False: self.save())
        self.tabs.currentChanged.connect(self._tab_changed)
        base = state.load_base_settings()
        self.h.set_style(base.subtitles.style_h)
        self.v.set_style(base.subtitles.style_v)
        self._doc_source: PreviewSource | None = None
        self._queue_video: Path | None = None
        for ed in (self.h, self.v):
            ed.edited.connect(lambda: self.saved.setText("Alterações não salvas"))

    def _tab_changed(self, _i: int) -> None:
        for ed in (self.h, self.v):
            if ed is not self.tabs.currentWidget():
                ed.pause()
        self.tabs.currentWidget().refresh()

    # ------------------------------------------------------------------ fonte da previa
    def _apply_source(self, src: PreviewSource) -> None:
        self.h.set_source(src)
        self.v.set_source(src)

    def set_background(self, video: Path | None) -> None:
        """Primeiro video da fila de Processar aulas."""
        self._queue_video = video
        doc = self._doc_source
        if video is None and doc is not None:
            return  # sem fila: continua mostrando o video revisado
        if doc is not None and video is not None and Path(video) == doc.video:
            self._apply_source(doc)
            return
        if video is None:
            self._apply_source(PreviewSource())
            return
        from ..adapters import ffmpeg as ff

        run_task(lambda _p: ff.probe(Path(video)).duration,
                 on_done=lambda d, v=video: self._queue_probed(Path(v), d),
                 on_error=lambda _e, v=video: self._queue_probed(Path(v), 0.0))

    def _queue_probed(self, video: Path, duration: float) -> None:
        if video == self._queue_video:
            self._apply_source(PreviewSource(video=video if duration else None, duration=duration))

    def set_doc(self, doc) -> None:
        """Legendas abertas em Revisar legendas: a previa passa a usar o texto e o tempo reais."""
        video = Path(doc.video)
        if not video.exists():
            return
        duration = max((c.end for c in doc.captions), default=0.0)
        from ..adapters import ffmpeg as ff

        def _probe(_p) -> float:
            try:
                return ff.probe(video).duration
            except Exception:  # noqa: BLE001
                return duration

        def _done(d: float) -> None:
            self._doc_source = PreviewSource(video=video, duration=d, segments=list(doc.captions),
                                             keywords=list(doc.keywords))
            self._apply_source(self._doc_source)

        run_task(_probe, on_done=_done)

    def save(self) -> None:
        try:
            s = state.compose(state.load_base_settings(), {"subtitles": {
                "style_h": self.h.style().model_dump(), "style_v": self.v.style().model_dump()}})
        except Exception as exc:  # noqa: BLE001
            self.saved.setText(f"Valor inválido: {exc}")
            return
        state.save_base_settings(s)
        self.saved.setText("Salvo ✓")
