"""浅色现代卡片风主题：设计令牌 + 全局 QSS。

设计约束（历史教训，勿改）：

- 不使用 ``WA_TranslucentBackground`` 与 ``QGraphicsDropShadowEffect``。
  分层窗口在部分 Windows 环境下会让整窗 alpha=0，既透明又鼠标点击穿透。
  层次一律用"底色 + 白色卡片 + 浅灰填充块"与 1px 低对比描边表达。
- 字号统一用 ``px``（QSS + 应用字体都用 px），避免 pt/px 混用导致高 DPI 比例不一致。
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QApplication, QWidget

# --------------------------------------------------------------------------- 字体

FONT_STACK = (
    '"Source Han Sans SC", "Noto Sans SC", "思源黑体", "PingFang SC", '
    '"Noto Sans", "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", sans-serif'
)

# --------------------------------------------------------------------------- 颜色令牌

PRIMARY = "#2563EB"
PRIMARY_HOVER = "#1D4ED8"
PRIMARY_PRESSED = "#1E40AF"
PRIMARY_SOFT = "#DBEAFE"
PRIMARY_TINT = "#EFF6FF"

BG_WHITE = "#FFFFFF"
BG_PAGE = "#FBFCFD"
BG_SOFT = "#F7F8FA"
BG_MUTE = "#F1F3F6"

TEXT_MAIN = "#1F2328"
TEXT_SUB = "#6B7280"
TEXT_MUTE = "#9CA3AF"
TEXT_INVERT = "#FFFFFF"

BORDER = "#E8EAEE"
BORDER_STRONG = "#D9DDE3"

SUCCESS = "#16A34A"
SUCCESS_SOFT = "#DCFCE7"
SUCCESS_TEXT = "#15803D"
DANGER = "#DC2626"
DANGER_SOFT = "#FEE2E2"
DANGER_TEXT = "#B91C1C"
WARNING = "#F59E0B"
WARNING_SOFT = "#FEF3C7"
WARNING_TEXT = "#B45309"
OFFLINE = "#9CA3AF"
OFFLINE_SOFT = "#F1F3F6"

# 提示条等级（tipLabel[level=...]）
TONE_BG = {
    "success": SUCCESS_SOFT,
    "primary": PRIMARY_TINT,
    "warning": WARNING_SOFT,
    "danger": DANGER_SOFT,
    "muted": OFFLINE_SOFT,
}
TONE_FG = {
    "success": SUCCESS_TEXT,
    "primary": PRIMARY_PRESSED,
    "warning": WARNING_TEXT,
    "danger": DANGER_TEXT,
    "muted": TEXT_SUB,
}

# --------------------------------------------------------------------------- 尺寸令牌

RADIUS_CARD = 12
RADIUS_CONTROL = 10
RADIUS_SMALL = 8

GAP_XS = 4
GAP_SM = 6
GAP_MD = 10
GAP_LG = 14
GAP_XL = 18

WINDOW_WIDTH = 480
DIALOG_WIDTH = 520

# --------------------------------------------------------------------------- 状态元数据


@dataclass(frozen=True)
class StateStyle:
    """一个运行状态对应的展示信息。"""

    text: str      # 中文文案
    tone: str      # success / primary / warning / danger / muted
    color: str     # 主色
    tint: str      # 浅色底
    glyph: str     # 图标类型：check / clock / alert / off


STATE_STYLES: dict[str, StateStyle] = {
    "online": StateStyle("已连接", "success", SUCCESS, SUCCESS_SOFT, "check"),
    "logging": StateStyle("认证中", "primary", PRIMARY, PRIMARY_TINT, "clock"),
    "need_login": StateStyle("待认证", "warning", WARNING, WARNING_SOFT, "clock"),
    "no_credential": StateStyle("未保存账号", "warning", WARNING, WARNING_SOFT, "alert"),
    "failed": StateStyle("认证失败", "danger", DANGER, DANGER_SOFT, "alert"),
    "credential_error": StateStyle("账号异常", "danger", DANGER, DANGER_SOFT, "alert"),
    "offline": StateStyle("非校园网", "muted", OFFLINE, OFFLINE_SOFT, "off"),
    "no_network": StateStyle("无网络", "muted", OFFLINE, OFFLINE_SOFT, "off"),
}

DEFAULT_STATE_STYLE = StateStyle("未知", "muted", OFFLINE, OFFLINE_SOFT, "alert")

# 兼容旧引用
STATE_COLORS: dict[str, str] = {state: style.color for state, style in STATE_STYLES.items()}
STATE_TEXT: dict[str, str] = {state: style.text for state, style in STATE_STYLES.items()}


def state_style(state: str) -> StateStyle:
    return STATE_STYLES.get(state, DEFAULT_STATE_STYLE)


def state_color(state: str) -> QColor:
    return QColor(state_style(state).color)


# --------------------------------------------------------------------------- 全局 QSS

QSS = f"""
QWidget {{
    font-family: {FONT_STACK};
    font-size: 13px;
    color: {TEXT_MAIN};
    background: transparent;
}}

QWidget#root {{
    background: {BG_PAGE};
    border: 1px solid {BORDER};
}}

QWidget#titleBar {{
    background: {BG_PAGE};
    border-bottom: 1px solid {BORDER};
}}

QLabel#appTitle {{
    color: {TEXT_MAIN};
    font-size: 14px;
    font-weight: 600;
}}

/* ---------- 卡片 ---------- */

QFrame#statusCard, QWidget#statusCard {{
    background: {BG_WHITE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CARD}px;
}}

QFrame#formCard, QWidget#formCard {{
    background: {BG_WHITE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CARD}px;
}}

QFrame#sectionCard, QWidget#sectionCard {{
    background: {BG_WHITE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CARD}px;
}}

QLabel#sectionTitle {{
    color: {TEXT_MAIN};
    font-size: 13px;
    font-weight: 600;
}}

/* ---------- 状态区 ---------- */

QLabel#statusTitle {{
    color: {TEXT_MAIN};
    font-size: 22px;
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

QLabel#statusPill {{
    border-radius: 9px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}}

QLabel#statusPill[tone="success"] {{ background: {SUCCESS_SOFT}; color: {SUCCESS_TEXT}; }}
QLabel#statusPill[tone="primary"] {{ background: {PRIMARY_TINT}; color: {PRIMARY_PRESSED}; }}
QLabel#statusPill[tone="warning"] {{ background: {WARNING_SOFT}; color: {WARNING_TEXT}; }}
QLabel#statusPill[tone="danger"]  {{ background: {DANGER_SOFT};  color: {DANGER_TEXT}; }}
QLabel#statusPill[tone="muted"]   {{ background: {OFFLINE_SOFT}; color: {TEXT_SUB}; }}

/* ---------- 表单 ---------- */

QLabel#fieldLabel {{
    color: {TEXT_SUB};
    font-size: 12px;
    font-weight: 500;
}}

QLabel#hintLabel {{
    color: {TEXT_MUTE};
    font-size: 11px;
}}

QWidget#inputFrame {{
    background: {BG_SOFT};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CONTROL}px;
}}

QWidget#inputFrame:hover {{
    border: 1px solid {BORDER_STRONG};
}}

QWidget#inputFrame[focused="true"] {{
    background: {BG_WHITE};
    border: 1px solid {PRIMARY};
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
    padding: 4px 8px;
    border-radius: {RADIUS_SMALL}px;
}}

QToolButton#revealButton:hover {{ color: {PRIMARY}; background: {BG_MUTE}; }}
QToolButton#revealButton:checked {{ color: {PRIMARY}; }}

/* ---------- 下拉框 ---------- */

QComboBox {{
    background: {BG_SOFT};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CONTROL}px;
    padding: 8px 30px 8px 12px;
    color: {TEXT_MAIN};
    font-size: 13px;
    min-height: 20px;
}}

QComboBox:hover {{ border: 1px solid {BORDER_STRONG}; background: {BG_WHITE}; }}
QComboBox:focus {{ border: 1px solid {PRIMARY}; background: {BG_WHITE}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ image: none; width: 0px; height: 0px; }}

QComboBox QAbstractItemView {{
    background: {BG_WHITE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CONTROL}px;
    padding: 4px;
    selection-background-color: {PRIMARY_TINT};
    selection-color: {PRIMARY_PRESSED};
    outline: none;
}}

/* ---------- 分段选择 ---------- */

QWidget#segmentBar {{
    background: {BG_MUTE};
    border-radius: {RADIUS_CONTROL}px;
}}

QPushButton#segment {{
    background: transparent;
    border: none;
    color: {TEXT_SUB};
    font-size: 12px;
    padding: 7px 6px;
    border-radius: {RADIUS_SMALL}px;
}}

QPushButton#segment:hover {{ color: {TEXT_MAIN}; }}

QPushButton#segment:checked {{
    background: {BG_WHITE};
    color: {PRIMARY_PRESSED};
    font-weight: 600;
}}

/* ---------- 按钮 ---------- */

QPushButton#primaryButton {{
    background: {PRIMARY};
    color: {TEXT_INVERT};
    border: none;
    border-radius: {RADIUS_CONTROL}px;
    font-size: 14px;
    font-weight: 600;
    padding: 11px 0px;
    min-height: 20px;
}}

QPushButton#primaryButton:hover {{ background: {PRIMARY_HOVER}; }}
QPushButton#primaryButton:pressed {{ background: {PRIMARY_PRESSED}; }}
QPushButton#primaryButton:disabled {{ background: {PRIMARY_SOFT}; color: {TEXT_INVERT}; }}

QPushButton#ghostButton {{
    background: transparent;
    border: none;
    color: {TEXT_SUB};
    font-size: 12px;
    padding: 6px 10px;
    border-radius: {RADIUS_SMALL}px;
}}

QPushButton#ghostButton:hover {{ background: {BG_MUTE}; color: {TEXT_MAIN}; }}
QPushButton#ghostButton:disabled {{ color: {TEXT_MUTE}; }}

QPushButton#outlineButton {{
    background: {BG_WHITE};
    border: 1px solid {BORDER_STRONG};
    border-radius: {RADIUS_SMALL}px;
    color: {TEXT_MAIN};
    font-size: 12px;
    font-weight: 500;
    padding: 7px 14px;
}}

QPushButton#outlineButton:hover {{ border: 1px solid {PRIMARY}; color: {PRIMARY_PRESSED}; }}

QPushButton#linkButton {{
    background: transparent;
    border: none;
    color: {TEXT_SUB};
    font-size: 12px;
    padding: 7px 12px;
    border-radius: {RADIUS_SMALL}px;
}}

QPushButton#linkButton:hover {{ background: {BG_MUTE}; color: {TEXT_MAIN}; }}
QPushButton#linkButton[tone="danger"]:hover {{ background: {DANGER_SOFT}; color: {DANGER_TEXT}; }}
QPushButton#linkButton[tone="primary"]:hover {{ background: {PRIMARY_TINT}; color: {PRIMARY_PRESSED}; }}

QPushButton#iconButton {{
    background: transparent;
    border: none;
    border-radius: {RADIUS_SMALL}px;
    color: {TEXT_MUTE};
    font-size: 13px;
}}

QPushButton#iconButton:hover {{ background: {BG_MUTE}; color: {TEXT_MAIN}; }}
QPushButton#closeButton:hover {{ background: {DANGER_SOFT}; color: {DANGER_TEXT}; }}

/* ---------- 提示 ---------- */

QLabel#tipLabel {{
    color: {TEXT_SUB};
    font-size: 12px;
    padding: 0px 2px;
}}

QLabel#tipLabel[level="success"] {{ color: {SUCCESS_TEXT}; }}
QLabel#tipLabel[level="error"] {{ color: {DANGER_TEXT}; }}
QLabel#tipLabel[level="info"] {{ color: {PRIMARY_PRESSED}; }}
QLabel#tipLabel[level="muted"] {{ color: {TEXT_MUTE}; }}

/* ---------- 弹窗内容 ---------- */

QDialog {{ background: {BG_PAGE}; }}
QMainWindow {{ background: {BG_PAGE}; }}

QCheckBox {{ color: {TEXT_MAIN}; font-size: 13px; spacing: 8px; }}

QListWidget {{
    background: {BG_WHITE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CONTROL}px;
    padding: 3px;
    color: {TEXT_MAIN};
    font-size: 12px;
    outline: none;
}}

QListWidget::item {{ padding: 8px; border-radius: {RADIUS_SMALL}px; }}
QListWidget::item:hover {{ background: {BG_SOFT}; }}
QListWidget::item:selected {{ background: {PRIMARY_TINT}; color: {PRIMARY_PRESSED}; }}

QTableWidget {{
    background: {BG_WHITE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CONTROL}px;
    gridline-color: {BORDER};
    color: {TEXT_MAIN};
    font-size: 12px;
    outline: none;
}}

QHeaderView::section {{
    background: {BG_SOFT};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px;
    color: {TEXT_SUB};
    font-size: 12px;
    font-weight: 600;
}}

QTableWidget::item {{ padding: 6px 8px; border: none; }}
QTableWidget::item:selected {{ background: {PRIMARY_TINT}; color: {PRIMARY_PRESSED}; }}

QTextBrowser, QTextEdit, QPlainTextEdit {{
    background: {BG_SOFT};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CONTROL}px;
    color: {TEXT_MAIN};
    font-size: 12px;
    padding: 10px;
}}

QScrollArea {{ background: transparent; border: none; }}

/* ---------- 滚动条 ---------- */

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {TEXT_MUTE}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ height: 0px; }}

/* ---------- 菜单与提示气泡 ---------- */

QMenu {{
    background: {BG_WHITE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CONTROL}px;
    padding: 5px;
}}

QMenu::item {{
    padding: 7px 22px 7px 14px;
    border-radius: {RADIUS_SMALL}px;
    color: {TEXT_MAIN};
    font-size: 12px;
}}

QMenu::item:selected {{ background: {PRIMARY_TINT}; color: {PRIMARY_PRESSED}; }}
QMenu::item:disabled {{ color: {TEXT_MUTE}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 8px; }}

QToolTip {{
    background: {TEXT_MAIN};
    color: {TEXT_INVERT};
    border: none;
    padding: 5px 9px;
    font-size: 12px;
}}

QMessageBox {{ background: {BG_WHITE}; }}
QMessageBox QLabel {{ color: {TEXT_MAIN}; font-size: 13px; }}
"""


def make_opaque(widget: QWidget) -> None:
    """强制不透明底。

    历史坑：窗口曾用 ``WA_TranslucentBackground`` 做圆角阴影，在部分 Windows
    环境下整窗 alpha=0，既透明又鼠标点击穿透。这里显式填底色兜底。
    """
    widget.setAutoFillBackground(True)
    palette = widget.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG_PAGE))
    widget.setPalette(palette)


def apply(app: QApplication) -> None:
    """应用全局字体与样式表（字号统一走 px）。"""
    font = QFont()
    font.setFamilies(
        [
            "Source Han Sans SC",
            "Noto Sans SC",
            "思源黑体",
            "PingFang SC",
            "Noto Sans",
            "Microsoft YaHei UI",
            "Microsoft YaHei",
            "Segoe UI",
        ]
    )
    font.setPixelSize(13)
    app.setFont(font)
    app.setStyleSheet(QSS)
