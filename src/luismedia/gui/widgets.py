"""Blocos visuais reaproveitados pelas paginas."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from . import theme


class Card(QFrame):
    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 14, 16, 14)
        self.body.setSpacing(6)
        if title:
            t = QLabel(title)
            t.setObjectName("cardTitle")
            self.body.addWidget(t)


def page_header(title: str, subtitle: str) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 6)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("pageTitle")
    s = QLabel(subtitle)
    s.setObjectName("pageSubtitle")
    s.setWordWrap(True)
    lay.addWidget(t)
    lay.addWidget(s)
    return w


def toggle(text: str, tip: str = "") -> QCheckBox:
    cb = QCheckBox(text)
    cb.setCursor(Qt.CursorShape.PointingHandCursor)
    if tip:
        cb.setToolTip(tip)
    return cb


def hint(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName("hint")
    lb.setWordWrap(True)
    return lb


def row(*widgets: QWidget, stretch_last: bool = False) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    for x in widgets:
        lay.addWidget(x)
    if not stretch_last:
        lay.addStretch(1)
    return w


def banner(label: QLabel, kind: str, text: str) -> None:
    colors = {"ok": (theme.SUCCESS, "rgba(52,211,153,0.12)"),
              "warn": (theme.WARNING, "rgba(251,191,36,0.12)"),
              "error": (theme.DANGER, "rgba(248,113,113,0.12)"),
              "info": (theme.ACCENT, "rgba(129,140,248,0.12)")}
    fg, bg = colors[kind]
    label.setStyleSheet(f"QLabel#banner {{ color: {fg}; background: {bg}; border: 1px solid {fg}; }}")
    label.setText(text)
    label.setVisible(bool(text))
