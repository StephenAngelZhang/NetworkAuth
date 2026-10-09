"""白色简洁风主题：配色常量与全局 QSS。"""

from __future__ import annotations

from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QApplication

FONT_FAMILY = '"Noto Sans", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif'

PRIMARY = "#2563EB"
PRIMARY_HOVER = "#1D4ED8"
PRIMARY_PRESSED = "#1E40AF"
PRIMARY_SOFT = "#DBEAFE"

BG_WHITE = "#FFFFFF"
BG_SOFT = "#F7F8FA"
BG_MUTE = "#F1F3F6"

TEXT_MAIN = "#1F2328"
TEXT_SUB = "#6B7280"
TEXT_MUTE = "#9CA3AF"
BORDER = "#E8EAEE"
BORDER_STRONG = "#D9DDE3"

SUCCESS = "#16A34A"
DANGER = "#DC2626"
WARNING = "#F59E0B"
OFFLINE = "#9CA3AF"

STATE_COLORS = {
    "online": PRIMARY,
    "logging": WARNING,
    "need_login": WARNING,
    "no_credential": WARNING,
    "failed": DANGER,
    "credential_error": DANGER,
    "offline": OFFLINE,
    "no_network": OFFLINE,
}

QSS = f"""
* {{ font-family: {FONT_FAMILY}; }}

QWidget#root {{
    background: {BG_WHITE};
    border: 1px solid {BORDER};
}}

QWidget#titleBar {{
    background: {BG_WHITE};
    border-bottom: 1px solid {BORDER};
}}

QLabel#appTitle {{
    color: {TEXT_MAIN};
    font-size: 14px;
    font-weight: 600;
}}

QLabel#fieldLabel {{
    color: {TEXT_SUB};
    font-size: 12px;
    font-weight: 500;
}}

QFrame#card, QWidget#card {{
    background: {BG_WHITE};
}}

QFrame#statusCard, QWidget#statusCard {{
    background: {BG_SOFT};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}

QFrame#formCard, QWidget#formCard {{
    background: {BG_WHITE};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}

QLabel#statusTitle {{
    color: {TEXT_MAIN};
    font-size: 20px;
    font-weight: 600;
}}

QLabel#statusSub {{
    color: {TEXT_SUB};
    font-size: 12px;
}}

QLabel#statusTime {{
    color: {TEXT_MUTE};
    font-size: 11px;
}}

QWidget#inputFrame {{
    background: {BG_WHITE};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}

QWidget#inputFrame[focused="true"] {{
    border: 1px solid {PRIMARY};
    background: #FFFFFF;
}}

QLineEdit {{
    background: transparent;
    border: none;
    color: {TEXT_MAIN};
    font-size: 13px;
    padding: 0px 2px;
    selection-background-color: {PRIMARY_SOFT};
    selection-color: {TEXT_MAIN};
}}

QLineEdit:disabled {{ color: {TEXT_MUTE}; }}

QToolButton#revealButton {{
    background: transparent;
    border: none;
    color: {TEXT_MUTE};
    font-size: 12px;
    padding: 4px 6px;
    border-radius: 6px;
}}

QToolButton#revealButton:hover {{ color: {PRIMARY}; background: {BG_MUTE}; }}

QComboBox {{
    background: {BG_WHITE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 8px 10px;
    color: {TEXT_MAIN};
    font-size: 13px;
    min-height: 20px;
}}

QComboBox:hover {{ border: 1px solid {BORDER_STRONG}; }}
QComboBox:focus {{ border: 1px solid {PRIMARY}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {BG_WHITE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 4px;
    selection-background-color: {PRIMARY_SOFT};
    selection-color: {TEXT_MAIN};
    outline: none;
}}

QWidget#segmentBar {{
    background: {BG_MUTE};
    border-radius: 10px;
}}

QPushButton#segment {{
    background: transparent;
    border: none;
    color: {TEXT_SUB};
    font-size: 12px;
    padding: 7px 6px;
    border-radius: 8px;
}}

QPushButton#segment:hover {{ color: {TEXT_MAIN}; }}
QPushButton#segment:checked {{
    background: {BG_WHITE};
    color: {TEXT_MAIN};
    font-weight: 600;
}}

QPushButton#primaryButton {{
    background: {PRIMARY};
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
    padding: 11px 0px;
}}

QPushButton#primaryButton:hover {{ background: {PRIMARY_HOVER}; }}
QPushButton#primaryButton:pressed {{ background: {PRIMARY_PRESSED}; }}
QPushButton#primaryButton:disabled {{ background: {PRIMARY_SOFT}; color: {TEXT_MUTE}; }}

QPushButton#ghostButton {{
    background: transparent;
    border: none;
    color: {TEXT_SUB};
    font-size: 12px;
    padding: 6px 10px;
    border-radius: 8px;
}}

QPushButton#ghostButton:hover {{ background: {BG_MUTE}; color: {TEXT_MAIN}; }}

QPushButton#iconButton {{
    background: transparent;
    border: none;
    border-radius: 8px;
    color: {TEXT_MUTE};
}}

QPushButton#iconButton:hover {{ background: {BG_MUTE}; color: {TEXT_MAIN}; }}

QLabel#tipLabel {{
    color: {TEXT_SUB};
    font-size: 12px;
    padding: 0px 2px;
}}

QLabel#tipLabel[level="success"] {{ color: {SUCCESS}; }}
QLabel#tipLabel[level="error"] {{ color: {DANGER}; }}
QLabel#tipLabel[level="info"] {{ color: {PRIMARY}; }}

QDialog, QMainWindow {{ background: {BG_WHITE}; }}

QScrollArea {{ background: transparent; border: none; }}

QTableWidget {{
    background: {BG_WHITE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    gridline-color: {BORDER};
    color: {TEXT_MAIN};
    font-size: 12px;
    outline: none;
}}

QHeaderView::section {{
    background: {BG_SOFT};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 7px 8px;
    color: {TEXT_SUB};
    font-size: 12px;
    font-weight: 600;
}}

QTableWidget::item {{ padding: 6px 8px; }}
QTableWidget::item:selected {{ background: {PRIMARY_SOFT}; color: {TEXT_MAIN}; }}

QTextBrowser, QTextEdit, QPlainTextEdit {{
    background: {BG_SOFT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    color: {TEXT_MAIN};
    font-size: 12px;
    padding: 8px;
}}

QListWidget {{
    background: {BG_WHITE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 4px;
    color: {TEXT_MAIN};
    font-size: 12px;
    outline: none;
}}

QListWidget::item {{ padding: 7px 8px; border-radius: 8px; }}
QListWidget::item:selected {{ background: {PRIMARY_SOFT}; color: {TEXT_MAIN}; }}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px 0px 2px 0px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {TEXT_MUTE}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar:horizontal {{ height: 0px; }}

QToolTip {{
    background: {TEXT_MAIN};
    color: #FFFFFF;
    border: none;
    padding: 4px 8px;
    font-size: 12px;
}}
"""


def state_color(state: str) -> QColor:
    return QColor(STATE_COLORS.get(state, OFFLINE))


def apply(app: QApplication) -> None:
    """应用全局字体与样式表。"""
    font = QFont()
    font.setFamilies(
        ["Noto Sans", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"]
    )
    font.setPointSize(9)
    app.setFont(font)
    app.setStyleSheet(QSS)
