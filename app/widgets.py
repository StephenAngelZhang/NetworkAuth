"""轻量自定义控件：开关、分段选择、状态呼吸点、输入框容器。"""

from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from app import theme


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
        self.setProperty("focused", "false")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(6)

        self.edit = _InnerLineEdit(self)
        self.edit.setPlaceholderText(placeholder)
        self.edit.setMinimumHeight(22)
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


# --------------------------------------------------------------------------- 开关


class Switch(QAbstractButton):
    """蓝色圆角滑块开关。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(46, 26)
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
        progress = self._offset

        track = QColor(
            int(self._off_color.red() + (self._on_color.red() - self._off_color.red()) * progress),
            int(self._off_color.green() + (self._on_color.green() - self._off_color.green()) * progress),
            int(self._off_color.blue() + (self._on_color.blue() - self._off_color.blue()) * progress),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(0, 0, width, height), radius, radius)

        margin = 3.0
        knob = height - margin * 2
        x = margin + progress * (width - margin * 2 - knob)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(x, margin, knob, knob))


# --------------------------------------------------------------------------- 分段选择


class SegmentedControl(QWidget):
    """横向分段按钮组。"""

    currentTextChanged = pyqtSignal(str)

    def __init__(self, options: list[str] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("segmentBar")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(3, 3, 3, 3)
        self._layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []
        self.setOptions(options or [])

    def setOptions(self, options: list[str]) -> None:
        for button in self._buttons:
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

        # 让 QButtonGroup 的信号只连接一次
        try:
            self._group.idClicked.disconnect()
        except (TypeError, RuntimeError):
            pass
        self._group.idClicked.connect(self._on_clicked)

        if self._buttons:
            self._buttons[0].setChecked(True)

    def _on_clicked(self, _index: int) -> None:
        self.currentTextChanged.emit(self.currentText())

    def currentText(self) -> str:
        button = self._group.checkedButton()
        return button.text() if button else ""

    def setCurrentText(self, text: str) -> None:
        for button in self._buttons:
            if button.text() == text:
                button.setChecked(True)
                return
        if self._buttons:
            self._buttons[0].setChecked(True)


# --------------------------------------------------------------------------- 状态呼吸点


class StatusDot(QWidget):
    """带呼吸光晕的状态色点。"""

    def __init__(self, size: int = 12, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size * 3, size * 3)
        self._color = QColor(theme.OFFLINE)
        self._pulse = 0.0
        self._animation = QPropertyAnimation(self, b"pulse", self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(1600)
        self._animation.setLoopCount(-1)
        self._animation.start()

    def get_pulse(self) -> float:
        return self._pulse

    def set_pulse(self, value: float) -> None:
        self._pulse = float(value)
        self.update()

    pulse = pyqtProperty(float, fget=get_pulse, fset=set_pulse)

    def setColor(self, color: QColor | str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        radius = self._size / 2.0

        wave = self._pulse
        halo_alpha = int(70 * (1.0 - wave))
        if halo_alpha > 0:
            halo = QColor(self._color)
            halo.setAlpha(halo_alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(halo)
            halo_radius = radius + radius * 1.1 * wave
            painter.drawEllipse(center, halo_radius, halo_radius)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        painter.drawEllipse(center, radius, radius)


# --------------------------------------------------------------------------- 细进度条


class BusyBar(QWidget):
    """登录进行中的细进度条。"""

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
        painter.setBrush(QColor(theme.BORDER))
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 1.5, 1.5)

        span = self.width() * 0.34
        start = self._value * (self.width() - span)
        gradient = QLinearGradient(start, 0, start + span, 0)
        gradient.setColorAt(0, QColor(theme.PRIMARY_SOFT))
        gradient.setColorAt(0.5, QColor(theme.PRIMARY))
        gradient.setColorAt(1, QColor(theme.PRIMARY_SOFT))
        painter.setBrush(gradient)
        painter.drawRoundedRect(QRectF(start, 0, span, self.height()), 1.5, 1.5)


# --------------------------------------------------------------------------- 圆角路径工具


def rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def divider_pen(color: str = theme.BORDER, width: float = 1.0) -> QPen:
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    return pen


def heading_font(size: int = 14, weight: int = 600) -> QFont:
    font = QFont()
    font.setPointSize(size)
    font.setWeight(weight)
    return font
