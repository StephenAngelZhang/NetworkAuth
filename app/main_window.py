"""主窗口：状态卡片、登录表单、操作按钮。"""

from __future__ import annotations

import time
from typing import Optional

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from app import icons, theme
from app.widgets import BusyBar, InputFrame, SegmentedControl, StatusDot, Switch
from core import autostart, network
from core.config import ConfigStore, Profile
from core.daemon import Daemon
from core.portal import DEFAULT_CARRIERS


STATE_TEXT = {
    "online": "已连接",
    "logging": "认证中",
    "need_login": "待认证",
    "no_credential": "未保存账号",
    "failed": "认证失败",
    "credential_error": "账号异常",
    "offline": "非校园网",
    "no_network": "无网络",
}


def _force_opaque(widget: QWidget) -> None:
    """强制不透明：分层窗口若整窗 alpha=0 会导致透明且鼠标点击穿透。"""
    widget.setAutoFillBackground(True)
    palette = widget.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#FFFFFF"))
    widget.setPalette(palette)


class TitleBar(QWidget):
    """自定义标题栏，支持拖拽。"""

    minimizeClicked = pyqtSignal()
    closeClicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(50)
        self._drag_pos: Optional[QPoint] = None
        self._window_start = QPoint()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 12, 0)
        layout.setSpacing(8)

        icon = QLabel(self)
        icon.setPixmap(icons.render_pixmap(22))
        icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        title = QLabel("校园网自动登录", self)
        title.setObjectName("appTitle")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addStretch()

        self._btn_min = QPushButton("—", self)
        self._btn_min.setObjectName("iconButton")
        self._btn_min.setFixedSize(32, 32)
        self._btn_min.setToolTip("最小化到托盘")
        self._btn_min.clicked.connect(self.minimizeClicked)

        self._btn_close = QPushButton("✕", self)
        self._btn_close.setObjectName("iconButton")
        self._btn_close.setFixedSize(32, 32)
        self._btn_close.setToolTip("隐藏到托盘")
        self._btn_close.clicked.connect(self.closeClicked)

        layout.addWidget(self._btn_min)
        layout.addWidget(self._btn_close)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
            self._window_start = self.window().pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_pos is not None:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.window().move(self._window_start + delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    settingsRequested = pyqtSignal()
    logsRequested = pyqtSignal()

    def __init__(
        self,
        store: ConfigStore,
        daemon: Daemon,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.store = store
        self.daemon = daemon
        self._carrier_map: dict[str, str] = dict(DEFAULT_CARRIERS)
        self._current_network_id: str = ""

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setWindowIcon(icons.app_icon())
        self.setFixedWidth(480)
        self.setWindowTitle("校园网自动登录")

        self._build_ui()
        self._connect_daemon()
        self._refresh_networks()
        self.adjustSize()
        self.setFixedHeight(self.height())

    def _build_ui(self) -> None:
        central = QWidget(self)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)

        self._root = QFrame(central)
        self._root.setObjectName("root")
        _force_opaque(central)
        _force_opaque(self._root)

        outer.addWidget(self._root)
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(self._root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._title_bar = TitleBar(self._root)
        self._title_bar.minimizeClicked.connect(self._hide_to_tray)
        self._title_bar.closeClicked.connect(self._hide_to_tray)
        root_layout.addWidget(self._title_bar)

        body = QWidget(self._root)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 16, 20, 18)
        body_layout.setSpacing(14)
        root_layout.addWidget(body)

        # 状态卡片
        status_card = QWidget(body)
        status_card.setObjectName("statusCard")
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(18, 16, 18, 16)
        status_layout.setSpacing(14)

        self._dot = StatusDot(14, status_card)
        self._dot.setColor(theme.OFFLINE)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        self._status_title = QLabel("正在初始化…", status_card)
        self._status_title.setObjectName("statusTitle")
        self._status_sub = QLabel("等待网络检测", status_card)
        self._status_sub.setObjectName("statusSub")
        self._status_time = QLabel("", status_card)
        self._status_time.setObjectName("statusTime")
        text_layout.addWidget(self._status_title)
        text_layout.addWidget(self._status_sub)
        text_layout.addWidget(self._status_time)
        text_layout.addStretch()

        status_layout.addWidget(self._dot)
        status_layout.addLayout(text_layout, 1)
        body_layout.addWidget(status_card)

        # 表单卡片
        form_card = QWidget(body)
        form_card.setObjectName("formCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(18, 16, 18, 16)
        form_layout.setSpacing(14)

        # 当前网络
        form_layout.addLayout(self._field_layout("当前网络", self._build_network_row()))

        # 学号
        self._user_input = InputFrame(placeholder="请输入学号")
        form_layout.addLayout(self._field_layout("学号", self._user_input))

        # 密码
        self._pass_input = InputFrame(placeholder="请输入密码", password=True)
        form_layout.addLayout(self._field_layout("密码", self._pass_input))

        # 服务类型
        self._segment = SegmentedControl([name for name, _ in DEFAULT_CARRIERS], form_card)
        form_layout.addLayout(self._field_layout("服务类型", self._segment))

        # 开关行
        switch_row = QHBoxLayout()
        switch_row.setSpacing(18)
        self._remember_switch = Switch(form_card)
        self._remember_switch.setChecked(True)
        self._bind_switch = Switch(form_card)
        self._bind_switch.setChecked(True)
        switch_row.addLayout(self._switch_layout("记住密码并自动登录", self._remember_switch))
        switch_row.addLayout(self._switch_layout("绑定当前网络", self._bind_switch))
        switch_row.addStretch()
        form_layout.addLayout(switch_row)

        body_layout.addWidget(form_card)

        # 登录按钮
        self._btn_login = QPushButton("登录", body)
        self._btn_login.setObjectName("primaryButton")
        self._btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_login.clicked.connect(self._on_login)
        body_layout.addWidget(self._btn_login)

        # 进度条（常驻占位，避免布局跳动）
        self._busy = BusyBar(body)
        body_layout.addWidget(self._busy)

        # 提示条
        self._tip = QLabel(" ", body)
        self._tip.setObjectName("tipLabel")
        self._tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tip.setMinimumHeight(18)
        body_layout.addWidget(self._tip)

        # 底部链接行：注销 / 设置 / 日志
        bottom = QHBoxLayout()
        bottom.setSpacing(4)
        self._btn_logout = QPushButton("注销", body)
        self._btn_logout.setObjectName("ghostButton")
        self._btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_logout.clicked.connect(self._on_logout)
        btn_settings = QPushButton("设置", body)
        btn_settings.setObjectName("ghostButton")
        btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_settings.clicked.connect(self.settingsRequested.emit)
        btn_logs = QPushButton("日志", body)
        btn_logs.setObjectName("ghostButton")
        btn_logs.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_logs.clicked.connect(self.logsRequested.emit)
        bottom.addStretch()
        bottom.addWidget(self._btn_logout)
        bottom.addWidget(btn_settings)
        bottom.addWidget(btn_logs)
        bottom.addStretch()
        body_layout.addLayout(bottom)

    def _field_layout(self, label: str, widget: QWidget) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(6)
        lbl = QLabel(label)
        lbl.setObjectName("fieldLabel")
        layout.addWidget(lbl)
        layout.addWidget(widget)
        return layout

    def _switch_layout(self, label: str, switch: Switch) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(6)
        layout.addWidget(switch)
        lbl = QLabel(label)
        lbl.setObjectName("statusSub")
        layout.addWidget(lbl)
        layout.addStretch()
        return layout

    def _build_network_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._network_combo = QComboBox(row)
        self._network_combo.setMinimumHeight(36)
        self._network_combo.currentIndexChanged.connect(self._on_network_changed)

        self._btn_refresh = QPushButton("刷新", row)
        self._btn_refresh.setObjectName("ghostButton")
        self._btn_refresh.setFixedWidth(48)
        self._btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_refresh.clicked.connect(self._refresh_networks)

        layout.addWidget(self._network_combo, 1)
        layout.addWidget(self._btn_refresh)
        return row

    def _connect_daemon(self) -> None:
        self.daemon.statusChanged.connect(self._on_status)
        self.daemon.loginFinished.connect(self._on_login_finished)
        self.daemon.logoutFinished.connect(self._on_logout_finished)
        self.daemon.portalConfig.connect(self._on_portal_config)

    def _on_portal_config(self, config) -> None:
        self._carrier_map = dict(config.carriers)
        self._segment.setOptions(config.carrier_names())

    def _refresh_networks(self) -> None:
        current = network.current_network()
        saved = self.store.saved_networks()

        self._network_combo.blockSignals(True)
        self._network_combo.clear()

        if current.connected:
            self._network_combo.addItem(f"当前：{current.label}", current.id)
            self._current_network_id = current.id
        else:
            self._current_network_id = ""

        seen = {current.id} if current.connected else set()
        for nid, username, carrier in saved:
            if nid in seen:
                continue
            label = self._network_label(nid, username, carrier)
            self._network_combo.addItem(label, nid)
            seen.add(nid)

        if not current.connected:
            self._network_combo.addItem("未检测到网络", "")
        self._network_combo.blockSignals(False)
        self._on_network_changed()

    def _network_label(self, nid: str, username: str, carrier: str) -> str:
        name = nid[5:] if nid.startswith("ssid:") else "有线网络"
        return f"{name} · {username}({carrier})"

    def _on_network_changed(self) -> None:
        network_id = self._network_combo.currentData() or ""
        profile = self.store.profile_for(network_id) or self.store.resolve(network_id)
        if profile and profile.valid:
            self._user_input.setText(profile.username)
            self._pass_input.setText(profile.password)
            self._segment.setCurrentText(profile.carrier)
        else:
            self._user_input.clear()
            self._pass_input.clear()
            self._segment.setCurrentText("校园用户")

    def _suffix_for(self, carrier: str) -> str:
        return self._carrier_map.get(carrier, "")

    def _on_login(self) -> None:
        username = self._user_input.text().strip()
        password = self._pass_input.text()
        if not username or not password:
            self._set_tip("error", "请填写学号和密码")
            return

        carrier = self._segment.currentText()
        suffix = self._suffix_for(carrier)
        profile = Profile(username=username, carrier=carrier, suffix=suffix)
        profile.password = password

        bind_to = self._network_combo.currentData() if self._bind_switch.isChecked() else None
        save = self._remember_switch.isChecked()

        self._set_busy(True)
        self.daemon.unblock()
        self.daemon.request_login(profile=profile, bind_to=bind_to, save=save)
        self._set_tip("info", "正在认证，请稍候…")

    def _on_logout(self) -> None:
        self.daemon.request_logout()
        self._set_tip("info", "正在注销…")

    def _set_busy(self, busy: bool) -> None:
        self._btn_login.setEnabled(not busy)
        self._btn_logout.setEnabled(not busy)
        if busy:
            self._busy.start()
        else:
            self._busy.stop()

    def _on_login_finished(self, ok: bool, message: str) -> None:
        self._set_busy(False)
        self._set_tip("success" if ok else "error", message)
        if ok:
            self._refresh_networks()

    def _on_logout_finished(self, ok: bool, message: str) -> None:
        self._set_tip("success" if ok else "error", message)

    def _on_status(self, state: str, message: str, network_label: str) -> None:
        self._dot.setColor(theme.STATE_COLORS.get(state, theme.OFFLINE))
        self._status_title.setText(STATE_TEXT.get(state, "未知"))
        self._status_sub.setText(f"{network_label} · {message}")

        ts = self.daemon.last_login_ts
        if state == "online" and ts:
            self._status_time.setText(f"上次登录：{time.strftime('%H:%M:%S', time.localtime(ts))}")
        else:
            self._status_time.setText("")

        if state == "logging":
            self._set_busy(True)
        elif state != "online":
            self._set_busy(False)

    def _set_tip(self, level: str, text: str) -> None:
        self._tip.setProperty("level", level)
        self._tip.setText(text)
        self._tip.style().unpolish(self._tip)
        self._tip.style().polish(self._tip)

    def _hide_to_tray(self) -> None:
        self.hide()

    def closeEvent(self, event) -> None:  # noqa: N802
        event.ignore()
        self._hide_to_tray()

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self._refresh_networks()
