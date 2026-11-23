"""Editar o video editando o texto: a transcricao como documento.

- clicar numa palavra leva o video ate ela; a palavra falada fica destacada ao tocar
- selecionar e apertar Delete apaga o trecho do video (vira um corte "Apagado no texto")
- o que vai sair do video (pausas, vicios, regravacoes, apagados) aparece riscado
- selecionar texto riscado e "Restaurar" traz de volta
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QTextFormat
from PySide6.QtWidgets import QTextEdit

from ..core.cleanup import Cut
from ..core.models import Segment, Word
from . import theme
from .timeline import CUT_COLORS

PARAGRAPH_GAP_S = 1.5


def _mmss(t: float) -> str:
    t = max(0, int(t))
    return f"{t // 60:02d}:{t % 60:02d}"


class TranscriptEditor(QTextEdit):
    seek_requested = Signal(float)
    delete_requested = Signal(int, int)   # indice da primeira e da ultima palavra
    restore_requested = Signal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("transcript")
        self.setReadOnly(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse
                                     | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.setCursorWidth(2)
        self.words: list[Word] = []
        self.cut_flags: list[bool] = []
        self._pos: list[tuple[int, int]] = []   # posicao de cada palavra no texto
        self._current = -1
        f = QFont(self.font())
        f.setPointSizeF(11.5)
        self.setFont(f)

    # ------------------------------------------------------------------ conteudo
    def set_content(self, captions: Sequence[Segment], cuts: Sequence[Cut]) -> None:
        scroll = self.verticalScrollBar().value()
        on = sorted((c for c in cuts if c.enabled), key=lambda c: c.start)
        self.words, self.cut_flags, self._pos = [], [], []
        self.clear()
        cur = QTextCursor(self.document())
        block = cur.blockFormat()
        block.setLineHeight(150, 1)  # 1 = ProportionalHeight: texto mais arejado
        cur.setBlockFormat(block)
        normal = QTextCharFormat()
        normal.setForeground(QColor(theme.TEXT))
        stamp = QTextCharFormat()
        stamp.setForeground(QColor(theme.MUTED))
        sf = QFont(self.font())
        sf.setPointSizeF(8.5)
        stamp.setFont(sf)
        last_end = None
        for c in captions:
            if not c.words:
                continue
            if last_end is None or c.words[0].start - last_end >= PARAGRAPH_GAP_S:
                if last_end is not None:
                    cur.insertBlock(block)
                    cur.insertBlock(block)
                cur.insertText(f"{_mmss(c.words[0].start)}   ", stamp)
            elif self.words:
                cur.insertText(" ", normal)
            for k, w in enumerate(c.words):
                if k:
                    cur.insertText(" ", normal)
                mid = (w.start + w.end) / 2
                hit = next((x for x in on if x.start <= mid < x.end), None)
                fmt = QTextCharFormat(normal)
                if hit is not None:
                    col = QColor(CUT_COLORS.get(hit.kind, "#ef4444"))
                    col.setAlpha(200)
                    fmt.setForeground(col)
                    fmt.setFontStrikeOut(True)
                    fmt.setToolTip(f"Sai do vídeo: {hit.label or hit.kind}")
                a = cur.position()
                cur.insertText(w.text.strip(), fmt)
                self._pos.append((a, cur.position()))
                self.words.append(w)
                self.cut_flags.append(hit is not None)
            last_end = c.words[-1].end
        self.verticalScrollBar().setValue(scroll)
        self._current = -1
        self._paint_current()

    # ------------------------------------------------------------------ palavra atual
    def word_at(self, t: float) -> int:
        lo, hi = 0, len(self.words) - 1
        best = -1
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.words[mid].start <= t:
                best, lo = mid, mid + 1
            else:
                hi = mid - 1
        return best

    def set_playhead(self, t: float, follow: bool = False) -> None:
        i = self.word_at(t)
        if i != self._current:
            self._current = i
            self._paint_current(follow)

    def _paint_current(self, follow: bool = False) -> None:
        if not (0 <= self._current < len(self._pos)):
            self.setExtraSelections([])
            return
        a, b = self._pos[self._current]
        sel = QTextEdit.ExtraSelection()
        cur = QTextCursor(self.document())
        cur.setPosition(a)
        cur.setPosition(b, QTextCursor.MoveMode.KeepAnchor)
        sel.cursor = cur
        sel.format.setBackground(QColor(theme.ACCENT_STRONG))
        sel.format.setForeground(QColor("#ffffff"))
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, False)
        self.setExtraSelections([sel])
        if follow:
            vis = QTextCursor(self.document())
            vis.setPosition(a)
            rect = self.cursorRect(vis)
            if not self.viewport().rect().contains(rect):
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() + rect.top()
                                                  - self.viewport().height() // 3)

    # ------------------------------------------------------------------ selecao
    def selected_words(self) -> tuple[int, int] | None:
        cur = self.textCursor()
        if not cur.hasSelection():
            return None
        a, b = cur.selectionStart(), cur.selectionEnd()
        idx = [i for i, (x, y) in enumerate(self._pos) if x < b and y > a]
        return (idx[0], idx[-1]) if idx else None

    def select_words(self, i0: int, i1: int) -> None:
        cur = QTextCursor(self.document())
        cur.setPosition(self._pos[i0][0])
        cur.setPosition(self._pos[i1][1], QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cur)

    def selected_text(self) -> str:
        r = self.selected_words()
        return " ".join(w.text.strip() for w in self.words[r[0]:r[1] + 1]) if r else ""

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        super().mouseReleaseEvent(e)
        if e.button() == Qt.MouseButton.LeftButton and not self.textCursor().hasSelection():
            pos = self.cursorForPosition(e.position().toPoint()).position()
            i = next((k for k, (a, b) in enumerate(self._pos) if a <= pos <= b), -1)
            if i >= 0:
                self.seek_requested.emit(self.words[i].start)

    def keyPressEvent(self, e) -> None:  # noqa: N802
        k = e.key()
        if k in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            r = self.selected_words()
            if r:
                self.delete_requested.emit(*r)
            e.accept()
            return
        if k in (Qt.Key.Key_Space, Qt.Key.Key_J, Qt.Key.Key_K, Qt.Key.Key_L) and \
                not e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            e.ignore()  # atalhos do player ficam com a tela
            return
        super().keyPressEvent(e)
