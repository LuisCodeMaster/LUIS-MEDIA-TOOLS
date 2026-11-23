"""Tema escuro do app (mesma identidade da janela antiga: azul-noite + indigo)."""

from importlib import resources

_ASSETS = str(resources.files("luismedia.gui") / "assets").replace("\\", "/")

BG = "#12131c"
SIDEBAR = "#0e0f17"
SURFACE = "#1b1d29"
SURFACE_2 = "#242737"
BORDER = "#323548"
TEXT = "#eef1f7"
MUTED = "#98a2b8"
ACCENT = "#818cf8"
ACCENT_STRONG = "#6366f1"
SUCCESS = "#34d399"
WARNING = "#fbbf24"
DANGER = "#f87171"

QSS = f"""
* {{ font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif; font-size: 10pt; color: {TEXT}; }}
QMainWindow, QWidget#page {{ background: {BG}; }}
QWidget#sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
QLabel#appName {{ font-size: 13pt; font-weight: 700; }}
QLabel#appTag {{ color: {MUTED}; font-size: 8.5pt; }}
QLabel#pageTitle {{ font-size: 17pt; font-weight: 700; }}
QLabel#pageSubtitle {{ color: {MUTED}; }}
QLabel#cardTitle {{ font-size: 10.5pt; font-weight: 700; color: {ACCENT}; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#hint {{ color: {MUTED}; font-size: 9pt; }}
QLabel#banner {{ border-radius: 8px; padding: 10px 14px; }}

QListWidget#nav {{ background: transparent; border: none; outline: 0; }}
QListWidget#nav::item {{ padding: 10px 14px; margin: 2px 10px; border-radius: 8px; color: {MUTED}; }}
QListWidget#nav::item:hover {{ background: {SURFACE}; color: {TEXT}; }}
QListWidget#nav::item:selected {{ background: {SURFACE_2}; color: {TEXT}; border-left: 3px solid {ACCENT}; }}

QFrame#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#dropZone {{ background: {SURFACE}; border: 2px dashed {BORDER}; border-radius: 12px; }}
QFrame#dropZone[active="true"] {{ border-color: {ACCENT}; background: {SURFACE_2}; }}

QPushButton {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 7px 14px; }}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:disabled {{ color: #5d6478; border-color: {SURFACE_2}; }}
QPushButton#primary {{ background: {ACCENT_STRONG}; border: none; font-weight: 700; padding: 10px 22px; }}
QPushButton#primary:hover {{ background: {ACCENT}; }}
QPushButton#primary:disabled {{ background: #3a3d63; color: #8b90b8; }}
QPushButton#danger {{ background: transparent; border: 1px solid {DANGER}; color: {DANGER}; padding: 10px 18px; }}
QPushButton#danger:hover {{ background: rgba(248,113,113,0.12); }}
QPushButton#link {{ background: transparent; border: none; color: {ACCENT}; padding: 4px 6px; }}
QPushButton#link:hover {{ text-decoration: underline; }}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 6px 8px;
    selection-background-color: {ACCENT_STRONG};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: url({_ASSETS}/chevron-down.svg); width: 10px; height: 6px; }}
QSpinBox, QDoubleSpinBox {{ padding-right: 26px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right;
    width: 22px; border: none; background: transparent; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-origin: border; subcontrol-position: bottom right;
    width: 22px; border: none; background: transparent; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url({_ASSETS}/chevron-up.svg); width: 10px; height: 6px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url({_ASSETS}/chevron-down.svg); width: 10px; height: 6px; }}
QComboBox QAbstractItemView {{ background: {SURFACE_2}; border: 1px solid {BORDER}; selection-background-color: {ACCENT_STRONG}; }}
QPlainTextEdit#code {{ font-family: "Cascadia Code", "Consolas", "JetBrains Mono", monospace; font-size: 10pt; }}

QCheckBox {{ spacing: 9px; padding: 3px 0; }}
QCheckBox::indicator {{ width: 34px; height: 18px; image: url({_ASSETS}/toggle-off.svg); }}
QCheckBox::indicator:checked {{ image: url({_ASSETS}/toggle-on.svg); }}
QCheckBox::indicator:disabled {{ image: url({_ASSETS}/toggle-disabled.svg); }}
QCheckBox:disabled {{ color: #5d6478; }}

QTableWidget {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; gridline-color: transparent;
               alternate-background-color: #1f2130; }}
QTableWidget::item {{ padding: 6px; border: none; }}
QTableWidget::item:selected {{ background: {SURFACE_2}; color: {TEXT}; }}
QHeaderView::section {{ background: {SURFACE}; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
                        padding: 8px 6px; font-weight: 600; }}
QTableCornerButton::section {{ background: {SURFACE}; border: none; }}

QProgressBar {{ background: {SURFACE_2}; border: none; border-radius: 6px; height: 12px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT_STRONG}, stop:1 {ACCENT}); border-radius: 6px; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 8px 16px; margin-right: 4px;
               border-bottom: 2px solid transparent; font-weight: 600; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom-color: {ACCENT}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}
QSplitter::handle {{ background: transparent; width: 12px; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
/* ---- estilo das legendas: inspetor + monitor */
QFrame#inspector {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#stage {{ background: #0a0b11; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#divider {{ background: {BORDER}; border: none; }}
QLabel#caption {{ color: {MUTED}; font-size: 8pt; font-weight: 700; letter-spacing: 1px; }}
QLabel#monitor {{ background: transparent; }}
QLabel#timecode {{ color: {MUTED}; font-family: "Cascadia Code", "Consolas", monospace; font-size: 9pt; }}
QPushButton#seg {{ background: transparent; border: none; border-radius: 6px; padding: 6px 9px; color: {MUTED};
                  font-weight: 600; }}
QPushButton#seg:hover {{ color: {TEXT}; }}
QPushButton#seg:checked {{ background: {SURFACE_2}; color: {TEXT}; }}
QPushButton#swatch {{ border: 1px solid #5b6178; border-radius: 6px; padding: 0; }}
QPushButton#swatch:hover {{ border-color: {TEXT}; }}
QPushButton#swatch:disabled {{ border-color: {SURFACE_2}; }}
QPushButton#play {{ background: {TEXT}; color: #0a0b11; border: none; border-radius: 19px; font-size: 11pt;
                   font-weight: 700; padding: 0; }}
QPushButton#play:hover {{ background: #ffffff; }}
QPushButton#play:disabled {{ background: {SURFACE_2}; color: {MUTED}; }}
QToolButton#more {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px 10px;
                   font-size: 12pt; }}
QToolButton#more:hover {{ border-color: {ACCENT}; }}
QToolButton#more::menu-indicator {{ image: none; width: 0; }}
QMenu {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 7px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT_STRONG}; }}
QMenu::item:disabled {{ color: #5d6478; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 6px; }}
QSlider#timeline::groove:horizontal {{ height: 4px; background: {SURFACE_2}; border-radius: 2px; }}
QSlider#timeline::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider#timeline::handle:horizontal {{ background: {TEXT}; width: 12px; height: 12px; margin: -4px 0;
                                      border-radius: 6px; }}
QSlider#timeline::groove:horizontal:disabled {{ background: {SURFACE}; }}
QSlider#timeline::handle:horizontal:disabled {{ background: {BORDER}; }}
QPushButton#iconBtn {{ padding: 0; font-size: 12pt; font-weight: 700; }}
QWidget#timeline {{ border-radius: 8px; }}
QListWidget#cutsList {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; color: {TEXT};
                       padding: 4px; outline: none; }}
QListWidget#cutsList::item {{ padding: 6px 4px; border-radius: 6px; color: {TEXT}; }}
QListWidget#cutsList::item:selected {{ background: {SURFACE_2}; color: {TEXT}; }}
QLabel#heroTitle {{ font-size: 22pt; font-weight: 800; color: {TEXT}; }}
QLabel#dropIcon {{ font-size: 30pt; color: {ACCENT}; }}
QLabel#thumb {{ background: #0a0b11; border-radius: 8px; font-size: 26pt; }}
QPushButton#hero {{ background: {ACCENT_STRONG}; border: none; color: white; font-size: 11pt; font-weight: 700;
                   padding: 11px 26px; border-radius: 10px; }}
QPushButton#hero:hover {{ background: {ACCENT}; }}
QPushButton#hero:disabled {{ background: {SURFACE_2}; color: #5d6478; }}
QTextEdit#transcript {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 10px;
                       padding: 14px 16px; selection-background-color: #3b3f8f; }}
QToolTip {{ background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px; }}
"""
