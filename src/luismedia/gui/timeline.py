"""Linha do tempo da revisao: onda do audio, cortes (pausas/vicios) e blocos de legenda.

Faixas (de cima para baixo):
    regua de tempo
    onda do audio (cortes ligados aparecem riscados em vermelho por cima)
    cortes: chips clicaveis (liga/desliga)
    legendas: blocos arrastaveis (mover ou puxar as bordas)

Rolar = navegar · Ctrl+rolar = zoom · arrastar na onda = selecionar trecho (para cortar).
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..core.cleanup import Cut
from ..core.models import Segment
from . import theme

RULER, WAVE, CUTS, CAPS = 20, 64, 20, 38
PAD = 6
EDGE = 6          # px para pegar a borda de uma legenda
MIN_CAP = 0.2     # duracao minima de uma legenda (s)

CUT_COLORS = {"pausa": "#f59e0b", "vicio": "#ef4444", "inicio": "#f59e0b", "fim": "#f59e0b", "manual": "#a855f7"}


def fmt_ruler(t: float) -> str:
    m, s = divmod(int(t), 60)
    return f"{m}:{s:02d}"


class Timeline(QWidget):
    seek_requested = Signal(float)
    caption_selected = Signal(int)
    caption_edit_started = Signal(int)
    caption_edited = Signal(int, float, float, bool)   # indice, inicio, fim, terminou
    cut_toggled = Signal(int)
    selection_changed = Signal(float, float)           # (0, 0) = sem selecao

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("timeline")
        self.setMinimumHeight(RULER + WAVE + CUTS + CAPS + PAD * 2)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.duration = 0.0
        self.captions: list[Segment] = []
        self.cuts: list[Cut] = []
        self.env: Sequence[float] = []
        self.env_rate = 50.0
        self.playhead = 0.0
        self.selected = -1
        self.selection: tuple[float, float] | None = None
        self.offset = 0.0     # segundo no canto esquerdo
        self.pps = 40.0       # pixels por segundo
        self._drag: tuple[str, int, float, float, float] | None = None  # modo, idx, t0, start, end
        self._fitted = False

    # ------------------------------------------------------------------ dados
    def set_data(self, duration: float, captions: Sequence[Segment], cuts: Sequence[Cut]) -> None:
        self.duration = max(duration, max((c.end for c in captions), default=0.0), 0.1)
        self.captions = list(captions)
        self.cuts = list(cuts)
        if not self._fitted:
            self.zoom_to(0, min(self.duration, 30.0))
            self._fitted = True
        self._clamp()
        self.update()

    def reset_view(self) -> None:
        self._fitted = False
        self.selection = None
        self.selected = -1

    def set_envelope(self, env: Sequence[float], rate: float = 50.0) -> None:
        self.env, self.env_rate = env, rate
        self.update()

    def set_playhead(self, t: float, follow: bool = True) -> None:
        self.playhead = t
        if follow and not self._drag:
            right = self.offset + self._view_s()
            if t > right - self._view_s() * 0.1 or t < self.offset:
                self.offset = max(0.0, t - self._view_s() * 0.2)
                self._clamp()
        self.update()

    def set_selected(self, i: int) -> None:
        self.selected = i
        if 0 <= i < len(self.captions):
            c = self.captions[i]
            if c.start < self.offset or c.end > self.offset + self._view_s():
                self.offset = max(0.0, c.start - self._view_s() * 0.25)
                self._clamp()
        self.update()

    def clear_selection(self) -> None:
        self.selection = None
        self.selection_changed.emit(0.0, 0.0)
        self.update()

    # ------------------------------------------------------------------ geometria
    def _view_s(self) -> float:
        return max(0.1, self.width() / self.pps)

    def _clamp(self) -> None:
        self.offset = min(max(0.0, self.offset), max(0.0, self.duration - self._view_s() * 0.9))

    def x_of(self, t: float) -> float:
        return (t - self.offset) * self.pps

    def t_of(self, x: float) -> float:
        return min(max(0.0, self.offset + x / self.pps), self.duration)

    def zoom_to(self, a: float, b: float) -> None:
        w = max(200, self.width())
        self.pps = min(800.0, max(w / max(self.duration, 1.0), w / max(b - a, 0.5)))
        self.offset = a
        self._clamp()
        self.update()

    def zoom(self, factor: float, at_x: float | None = None) -> None:
        at_x = self.width() / 2 if at_x is None else at_x
        t = self.t_of(at_x)
        lo = self.width() / max(self.duration, 1.0)
        self.pps = min(800.0, max(lo, self.pps * factor))
        self.offset = t - at_x / self.pps
        self._clamp()
        self.update()

    def _lanes(self) -> dict[str, QRectF]:
        w = float(self.width())
        y = PAD
        out = {}
        for name, h in (("ruler", RULER), ("wave", WAVE), ("cuts", CUTS), ("caps", CAPS)):
            out[name] = QRectF(0, y, w, h)
            y += h
        return out

    def _cap_at(self, x: float) -> tuple[int, str] | None:
        t = self.t_of(x)
        tol = EDGE / self.pps
        for i, c in enumerate(self.captions):
            if c.start - tol <= t <= c.end + tol:
                if abs(t - c.start) <= tol:
                    return i, "start"
                if abs(t - c.end) <= tol:
                    return i, "end"
                if c.start <= t <= c.end:
                    return i, "move"
        return None

    def _cut_at(self, x: float) -> int:
        t = self.t_of(x)
        hits = [i for i, c in enumerate(self.cuts) if c.start <= t <= c.end]
        return min(hits, key=lambda i: self.cuts[i].duration) if hits else -1

    # ------------------------------------------------------------------ desenho
    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        lanes = self._lanes()
        p.fillRect(self.rect(), QColor("#0f1018"))
        self._paint_ruler(p, lanes["ruler"])
        self._paint_wave(p, lanes["wave"])
        self._paint_cuts(p, lanes["wave"], lanes["cuts"], lanes["caps"])
        self._paint_caps(p, lanes["caps"])
        if self.selection:
            a, b = self.selection
            r = QRectF(self.x_of(a), lanes["wave"].top(), (b - a) * self.pps,
                       lanes["caps"].bottom() - lanes["wave"].top())
            p.fillRect(r, QColor(129, 140, 248, 50))
            p.setPen(QPen(QColor("#818cf8"), 1))
            p.drawRect(r)
        x = self.x_of(self.playhead)
        p.setPen(QPen(QColor("#f8fafc"), 1.5))
        p.drawLine(QPointF(x, lanes["ruler"].top()), QPointF(x, lanes["caps"].bottom()))
        p.setBrush(QColor("#f8fafc"))
        p.setPen(Qt.PenStyle.NoPen)
        tri = QPainterPath()
        top = lanes["ruler"].top()
        tri.moveTo(x - 5, top)
        tri.lineTo(x + 5, top)
        tri.lineTo(x, top + 7)
        tri.closeSubpath()
        p.drawPath(tri)
        p.end()

    def _paint_ruler(self, p: QPainter, r: QRectF) -> None:
        p.setPen(QColor(theme.MUTED))
        f = QFont(self.font())
        f.setPointSizeF(7.5)
        p.setFont(f)
        step = next(s for s in (0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800) if s * self.pps >= 70)
        t = (int(self.offset / step)) * step
        while t <= self.offset + self._view_s():
            x = self.x_of(t)
            p.setPen(QColor("#2a2e3f"))
            p.drawLine(QPointF(x, r.bottom() - 5), QPointF(x, r.bottom()))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QPointF(x + 3, r.bottom() - 6), fmt_ruler(t) if step >= 1 else f"{t:.1f}")
            t += step

    def _paint_wave(self, p: QPainter, r: QRectF) -> None:
        p.fillRect(r, QColor("#141623"))
        mid = r.center().y()
        if not self.env:
            p.setPen(QColor("#2a2e3f"))
            p.drawLine(QPointF(0, mid), QPointF(r.right(), mid))
            return
        path = QPainterPath()
        n = len(self.env)
        top_pts, bot_pts = [], []
        for x in range(0, int(r.width()) + 1, 2):
            a = int(self.t_of(x) * self.env_rate)
            b = max(a + 1, int(self.t_of(x + 2) * self.env_rate))
            if a >= n:
                break
            v = max(self.env[a:min(b, n)] or [0.0])
            h = max(0.5, v * (r.height() / 2 - 3))
            top_pts.append(QPointF(x, mid - h))
            bot_pts.append(QPointF(x, mid + h))
        if not top_pts:
            return
        path.moveTo(top_pts[0])
        for pt in top_pts[1:]:
            path.lineTo(pt)
        for pt in reversed(bot_pts):
            path.lineTo(pt)
        path.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#5b6cf0"))
        p.drawPath(path)

    def _paint_cuts(self, p: QPainter, wave: QRectF, lane: QRectF, caps: QRectF) -> None:
        p.fillRect(lane, QColor("#0f1018"))
        f = QFont(self.font())
        f.setPointSizeF(7)
        p.setFont(f)
        for c in self.cuts:
            x0, x1 = self.x_of(c.start), self.x_of(c.end)
            if x1 < 0 or x0 > self.width():
                continue
            col = QColor(CUT_COLORS.get(c.kind, "#ef4444"))
            if c.enabled:
                shade = QColor(col)
                shade.setAlpha(70)
                p.fillRect(QRectF(x0, wave.top(), x1 - x0, caps.bottom() - wave.top()),
                           QBrush(shade, Qt.BrushStyle.SolidPattern))
                hatch = QColor(col)
                hatch.setAlpha(110)
                p.fillRect(QRectF(x0, wave.top(), x1 - x0, wave.height()), QBrush(hatch, Qt.BrushStyle.BDiagPattern))
            chip = QRectF(x0, lane.top() + 3, max(4.0, x1 - x0), lane.height() - 6)
            p.setPen(QPen(col, 1))
            fill = QColor(col)
            fill.setAlpha(200 if c.enabled else 0)
            p.setBrush(fill)
            p.drawRoundedRect(chip, 3, 3)
            if chip.width() > 26:
                p.setPen(QColor("#0b0c12") if c.enabled else col)
                p.drawText(chip.adjusted(4, 0, -2, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                           "✂" if chip.width() < 60 else ("✂ " + c.label))

    def _paint_caps(self, p: QPainter, r: QRectF) -> None:
        f = QFont(self.font())
        f.setPointSizeF(8)
        p.setFont(f)
        for i, c in enumerate(self.captions):
            x0, x1 = self.x_of(c.start), self.x_of(c.end)
            if x1 < 0 or x0 > self.width():
                continue
            box = QRectF(x0 + 0.5, r.top() + 3, max(3.0, x1 - x0 - 1), r.height() - 6)
            sel = i == self.selected
            p.setPen(QPen(QColor("#c7d2fe") if sel else QColor("#3b4160"), 1.5 if sel else 1))
            p.setBrush(QColor("#4f46e5") if sel else QColor("#23263a"))
            p.drawRoundedRect(box, 4, 4)
            if box.width() > 18:
                p.setPen(QColor("#ffffff") if sel else QColor("#c9cbe0"))
                p.drawText(box.adjusted(5, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                           p.fontMetrics().elidedText(c.text.replace("\n", " "), Qt.TextElideMode.ElideRight,
                                                      int(box.width() - 9)))

    # ------------------------------------------------------------------ mouse
    def wheelEvent(self, e) -> None:  # noqa: N802
        dy = e.angleDelta().y() or e.angleDelta().x()
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(1.25 if dy > 0 else 0.8, e.position().x())
        else:
            self.offset -= dy / 120 * self._view_s() * 0.15
            self._clamp()
            self.update()
        e.accept()

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() != Qt.MouseButton.LeftButton:
            return
        lanes = self._lanes()
        x, y = e.position().x(), e.position().y()
        t = self.t_of(x)
        if lanes["caps"].top() <= y <= lanes["caps"].bottom():
            hit = self._cap_at(x)
            if hit:
                i, mode = hit
                c = self.captions[i]
                self.selected = i
                self.caption_selected.emit(i)
                self.caption_edit_started.emit(i)
                self._drag = (mode, i, t, c.start, c.end)
                self.update()
                return
        if lanes["cuts"].top() <= y <= lanes["cuts"].bottom():
            k = self._cut_at(x)
            if k >= 0:
                self.cut_toggled.emit(k)
                return
        # regua/onda: posiciona a agulha e comeca uma selecao
        self.selection = None
        self._drag = ("select", -1, t, t, t)
        self.seek_requested.emit(t)
        self.update()

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        x = e.position().x()
        if self._drag is None:
            lanes = self._lanes()
            y = e.position().y()
            cur = Qt.CursorShape.ArrowCursor
            if lanes["caps"].top() <= y <= lanes["caps"].bottom():
                hit = self._cap_at(x)
                if hit:
                    cur = Qt.CursorShape.SizeHorCursor if hit[1] != "move" else Qt.CursorShape.OpenHandCursor
            elif lanes["cuts"].top() <= y <= lanes["cuts"].bottom() and self._cut_at(x) >= 0:
                cur = Qt.CursorShape.PointingHandCursor
                c = self.cuts[self._cut_at(x)]
                self.setToolTip(f"{c.label} · {c.duration:.2f} s · clique para {'manter' if c.enabled else 'cortar'}")
            else:
                cur = Qt.CursorShape.IBeamCursor
                self.setToolTip("Clique para posicionar · arraste para selecionar um trecho · Ctrl+rolar = zoom")
            self.setCursor(cur)
            return
        mode, i, t0, s0, e0 = self._drag
        t = self.t_of(x)
        if mode == "select":
            a, b = sorted((t0, t))
            self.selection = (a, b) if b - a > 0.05 else None
            self.update()
            return
        start, end = self._edited(mode, i, t - t0, s0, e0)
        self.captions[i] = self.captions[i].model_copy(update={"start": start, "end": end})
        self.caption_edited.emit(i, start, end, False)
        self.update()

    def _edited(self, mode: str, i: int, dt: float, s0: float, e0: float) -> tuple[float, float]:
        lo = self.captions[i - 1].end if i > 0 else 0.0
        hi = self.captions[i + 1].start if i + 1 < len(self.captions) else self.duration
        if mode == "start":
            return min(max(lo, s0 + dt), e0 - MIN_CAP), e0
        if mode == "end":
            return s0, max(min(hi, e0 + dt), s0 + MIN_CAP)
        dur = e0 - s0
        start = min(max(lo, s0 + dt), hi - dur)
        return start, start + dur

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if self._drag is None:
            return
        mode, i, *_ = self._drag
        self._drag = None
        if mode == "select":
            a, b = self.selection or (0.0, 0.0)
            self.selection_changed.emit(a, b)
        else:
            c = self.captions[i]
            self.caption_edited.emit(i, c.start, c.end, True)
        self.update()

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        self._clamp()
