"""轻量自定义控件：输入框、下拉框、开关、分段选择、状态徽标、细进度条。"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import (
    QEasingCurve,
    QLineF,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPalette, QPen
from PyQt6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app import icons, theme


def _blend(start: QColor, end: QColor, mix: float) -> QColor:
    """线性插值两个颜色，用于 180~200ms 的颜色过渡。"""
    ratio = max(0.0, min(1.0, float(mix)))
    return QColor(
        int(start.red() + (end.red() - start.red()) * ratio),
        int(start.green() + (end.green() - start.green()) * ratio),
        int(start.blue() + (end.blue() - start.blue()) * ratio),
    )


# --------------------------------------------------------------------------- 输入框


class _InnerLineEdit(QLineEdit):
    focusChanged = pyqtSignal(bool)

    def focusInEvent(self, event) -> None:  # noqa: N802
        super().focusInEvent(event)
        self.focusChanged.emit(True)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        self.focusChanged.emit(False)


class InputFrame(QWidget):
    """带圆角边框的输入框容器（可选密码显示切换）。"""

    textChanged = pyqtSignal(str)
    returnPressed = pyqtSignal()

    def __init__(
        self,
        placeholder: str = "",
        password: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("inputFrame")
        # 自定义 QWidget 子类必须显式开启，否则 QSS 的 background/border 不会绘制
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("focused", "false")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        self.edit = _InnerLineEdit(self)
        self.edit.setPlaceholderText(placeholder)
        self.edit.setMinimumHeight(20)
        palette = self.edit.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(theme.TEXT_MUTE))
        self.edit.setPalette(palette)
        if password:
            self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.edit)
        self.setFocusProxy(self.edit)

        self.reveal: QToolButton | None = None
        if password:
            self.reveal = QToolButton(self)
            self.reveal.setObjectName("revealButton")
            self.reveal.setText("显示")
            self.reveal.setCheckable(True)
            self.reveal.setCursor(Qt.CursorShape.PointingHandCursor)
            self.reveal.setToolTip("显示/隐藏密码")
            self.reveal.toggled.connect(self._on_reveal)
            layout.addWidget(self.reveal)

        self.edit.focusChanged.connect(self._on_focus)
        self.edit.textChanged.connect(self.textChanged)
        self.edit.returnPressed.connect(self.returnPressed)

    def _on_focus(self, focused: bool) -> None:
        self.setProperty("focused", "true" if focused else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def _on_reveal(self, shown: bool) -> None:
        self.edit.setEchoMode(
            QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
        )
        if self.reveal is not None:
            self.reveal.setText("隐藏" if shown else "显示")

    def text(self) -> str:
        return self.edit.text()

    def setText(self, value: str) -> None:
        self.edit.setText(value)

    def clear(self) -> None:
        self.edit.clear()

    def setPlaceholderText(self, value: str) -> None:
        self.edit.setPlaceholderText(value)


# --------------------------------------------------------------------------- 下拉框


class ComboBox(QComboBox):
    """统一样式的下拉框：QSS 关掉原生箭头，这里自绘一个细箭头。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(38)
        self.setMaxVisibleItems(10)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(theme.TEXT_SUB))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        center_x = self.width() - 16.0
        center_y = self.height() / 2.0
        painter.drawLine(QLineF(center_x - 4.0, center_y - 2.0, center_x, center_y + 2.0))
        painter.drawLine(QLineF(center_x, center_y + 2.0, center_x + 4.0, center_y - 2.0))
        painter.end()


# --------------------------------------------------------------------------- 开关


class Switch(QAbstractButton):
    """蓝色圆角滑块开关。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(44, 24)
        self._offset = 0.0
        self._on_color = QColor(theme.PRIMARY)
        self._off_color = QColor(theme.BORDER_STRONG)
        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.toggled.connect(self._on_toggled)

    def get_offset(self) -> float:
        return self._offset

    def set_offset(self, value: float) -> None:
        self._offset = float(value)
        self.update()

    offset = pyqtProperty(float, fget=get_offset, fset=set_offset)

    def _on_toggled(self, checked: bool) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._offset)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width, height = self.width(), self.height()
        radius = height / 2.0
        track = _blend(self._off_color, self._on_color, self._offset)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(0, 0, width, height), radius, radius)

        margin = 3.0
        knob = height - margin * 2
        x = margin + self._offset * (width - margin * 2 - knob)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(x, margin, knob, knob))


# --------------------------------------------------------------------------- 分段选择


class SegmentedControl(QWidget):
    """横向分段按钮组。"""

    currentTextChanged = pyqtSignal(str)

    def __init__(self, options: list[str] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("segmentBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(3, 3, 3, 3)
        self._layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []
        self.setOptions(options or [])

    def setOptions(self, options: list[str], keep_current: bool = True) -> None:
        """重建选项。

        ``keep_current=True`` 时会保留原有选中项——门户配置每次刷新都会调用这里，
        以前无条件选中第一项会把用户选好的服务类型悄悄改掉。
        """
        previous = self.currentText() if keep_current else ""

        for button in self._buttons:
            self._group.removeButton(button)
            self._layout.removeWidget(button)
            button.deleteLater()
        self._buttons.clear()

        for index, text in enumerate(options):
            button = QPushButton(text, self)
            button.setObjectName("segment")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._group.addButton(button, index)
            self._layout.addWidget(button)
            self._buttons.append(button)

        # 只断开自己的槽，避免误伤其他连接
        try:
            self._group.idClicked.disconnect(self._on_clicked)
        except (TypeError, RuntimeError):
            pass
        self._group.idClicked.connect(self._on_clicked)

        if previous and previous in options:
            self._check(previous)
        elif self._buttons:
            self._buttons[0].setChecked(True)

    def _check(self, text: str) -> None:
        for button in self._buttons:
            if button.text() == text:
                button.setChecked(True)
                return

    def _on_clicked(self, _index: int) -> None:
        self.currentTextChanged.emit(self.currentText())

    def currentText(self) -> str:
        button = self._group.checkedButton()
        return button.text() if button else ""

    def setCurrentText(self, text: str) -> None:
        if text and any(button.text() == text for button in self._buttons):
            self._check(text)
        elif self._buttons and not self._group.checkedButton():
            self._buttons[0].setChecked(True)


# --------------------------------------------------------------------------- 状态徽标


class StatusBadge(QWidget):
    """图标化状态徽标：浅色圆底 + 线性图标 + 呼吸光晕。"""

    def __init__(self, size: int = 48, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)

        self._glyph = "alert"
        self._color = QColor(theme.OFFLINE)
        self._tint = QColor(theme.OFFLINE_SOFT)
        self._intensity = 0.45
        self._pulse = 0.0
        self._from = (QColor(self._color), QColor(self._tint))
        self._to = (QColor(self._color), QColor(self._tint))
        self._badge = icons.badge_pixmap(
            self._glyph, size, self._color.name(), self._tint.name()
        )

        self._breath = QPropertyAnimation(self, b"pulse", self)
        self._breath.setStartValue(0.0)
        self._breath.setEndValue(1.0)
        self._breath.setDuration(1800)
        self._breath.setLoopCount(-1)
        self._breath.start()

        self._fade = QVariantAnimation(self)
        self._fade.setDuration(200)
        self._fade.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._fade.valueChanged.connect(self._on_fade)

    def get_pulse(self) -> float:
        return self._pulse

    def set_pulse(self, value: float) -> None:
        self._pulse = float(value)
        self.update()

    pulse = pyqtProperty(float, fget=get_pulse, fset=set_pulse)

    def setState(self, state: str) -> None:
        """按状态元数据切换图标与配色（认证中时呼吸更明显）。"""
        style = theme.state_style(state)
        self.apply(style.glyph, style.color, style.tint, 1.0 if state == "logging" else 0.45)

    def apply(self, glyph: str, color: str, tint: str, intensity: float = 0.45) -> None:
        self._glyph = glyph
        self._intensity = intensity
        self._from = (QColor(self._color), QColor(self._tint))
        self._to = (QColor(color), QColor(tint))
        self._fade.stop()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()

    def _on_fade(self, value) -> None:
        self._color = _blend(self._from[0], self._to[0], value)
        self._tint = _blend(self._from[1], self._to[1], value)
        self._badge = icons.badge_pixmap(
            self._glyph, self._size, self._color.name(), self._tint.name()
        )
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        alpha = int(70 * self._intensity * (1.0 - self._pulse))
        if alpha > 0:
            halo = QColor(self._color)
            halo.setAlpha(alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(halo)
            radius = self._size / 2.0 + self._size * 0.16 * self._pulse
            painter.drawEllipse(QPointF(self._size / 2.0, self._size / 2.0), radius, radius)

        painter.drawPixmap(0, 0, self._badge)
        painter.end()


# --------------------------------------------------------------------------- 细进度条


class BusyBar(QWidget):
    """登录进行中的细进度条（不确定进度）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(3)
        self._value = 0.0
        self._running = False
        self._timer = QTimer(self)
        self._timer.setInterval(28)
        self._timer.timeout.connect(self._step)

    def start(self) -> None:
        self._value = 0.0
        self._running = True
        self._timer.start()
        self.update()

    def stop(self) -> None:
        self._running = False
        self._timer.stop()
        self.update()

    def _step(self) -> None:
        self._value = (self._value + 0.02) % 1.0
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self._running:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.BG_MUTE))
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 1.5, 1.5)

        span = self.width() * 0.34
        start = self._value * (self.width() - span)
        gradient = QLinearGradient(start, 0, start + span, 0)
        gradient.setColorAt(0, QColor(theme.PRIMARY_SOFT))
        gradient.setColorAt(0.5, QColor(theme.PRIMARY))
        gradient.setColorAt(1, QColor(theme.PRIMARY_SOFT))
        painter.setBrush(gradient)
        painter.drawRoundedRect(QRectF(start, 0, span, self.height()), 1.5, 1.5)
        painter.end()


# --------------------------------------------------------------------------- 弹窗标题栏


class DialogHeader(QWidget):
    """无边框弹窗的标题栏：标题 + 关闭按钮，支持拖拽移动窗口。"""

    closeRequested = pyqtSignal()

    def __init__(self, title: str, parent: QWidget | None = None, height: int = 50) -> None:
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(height)
        self._drag_pos: Optional[QPoint] = None
        self._window_start = QPoint()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 12, 0)
        layout.setSpacing(8)

        label = QLabel(title, self)
        label.setObjectName("appTitle")
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(label)
        layout.addStretch()

        close = QPushButton("✕", self)
        close.setObjectName("closeButton")
        close.setFixedSize(30, 30)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setToolTip("关闭")
        close.clicked.connect(self.closeRequested)
        layout.addWidget(close)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
            self._window_start = self.window().pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_pos is not None:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.window().move(self._window_start + delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_pos = None
        super().mouseReleaseEvent(event)


# --------------------------------------------------------------------------- 小工具


def set_tone(widget: QWidget, tone: str) -> None:
    """设置动态属性 ``tone`` 并刷新样式（QSS 里用 [tone="..."] 匹配）。"""
    widget.setProperty("tone", tone)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def field_label(text: str, parent: QWidget | None = None) -> QLabel:
    """表单字段标题，避免各处重复三行代码。"""
    label = QLabel(text, parent)
    label.setObjectName("fieldLabel")
    return label


def v_field(label: str, widget: QWidget, spacing: int = theme.GAP_SM) -> QVBoxLayout:
    """"标题 + 控件"的纵向字段布局。"""
    layout = QVBoxLayout()
    layout.setSpacing(spacing)
    layout.addWidget(field_label(label, widget.parentWidget()))
    layout.addWidget(widget)
    return layout


def h_switch_row(label: str, switch: Switch) -> QHBoxLayout:
    """"开关 + 说明"的横向行布局。"""
    layout = QHBoxLayout()
    layout.setSpacing(theme.GAP_MD)
    layout.addWidget(switch)
    text = QLabel(label)
    text.setObjectName("statusSub")
    layout.addWidget(text)
    layout.addStretch()
    return layout
