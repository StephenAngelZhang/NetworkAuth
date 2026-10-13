"""主窗口：状态卡、登录表单、操作区与底部链接。

结构：标题栏 → 状态卡 → 表单卡 → 主按钮 → 细进度条 → 提示 → 底部链接行。
"""

from __future__ import annotations

import time
from typing import Optional

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import icons, theme
from app.widgets import (
    BusyBar,
    ComboBox,
    InputFrame,
    SegmentedControl,
    StatusBadge,
    Switch,
    field_label,
    h_switch_row,
    set_tone,
    v_field,
)
from core.config import ConfigStore, Profile
from core.daemon import Daemon
from core.portal import DEFAULT_CARRIERS


class TitleBar(QWidget):
    """自定义标题栏，支持拖拽。"""

    minimizeClicked = pyqtSignal()
    closeClicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("titleBar")
        # 自定义 QWidget 子类必须显式开启，否则 QSS 的 background/border 不会绘制
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(52)
        self._drag_pos: Optional[QPoint] = None
        self._window_start = QPoint()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 12, 0)
        layout.setSpacing(10)

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
        self._btn_min.setFixedSize(30, 30)
        self._btn_min.setToolTip("最小化")
        self._btn_min.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_min.clicked.connect(self.minimizeClicked)

        self._btn_close = QPushButton("✕", self)
        self._btn_close.setObjectName("closeButton")
        self._btn_close.setFixedSize(30, 30)
        self._btn_close.setToolTip("关闭")
        self._btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
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
    quitRequested = pyqtSignal()

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
        self._network_signature: tuple = ()
        self._next_poll_ts: Optional[float] = None
        self._is_busy = False

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setWindowIcon(icons.app_icon())
        self.setFixedWidth(theme.WINDOW_WIDTH)
        self.setWindowTitle("校园网自动登录")

        self._build_ui()
        self._connect_daemon()
        self._refresh_networks()
        self.adjustSize()
        self.setFixedHeight(self.height())
        self._sync_auto_login_pill()

        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._tick_countdown)
        self._countdown.start()

    # ------------------------------------------------------------------ 界面

    def _build_ui(self) -> None:
        central = QWidget(self)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)

        self._root = QFrame(central)
        self._root.setObjectName("root")
        theme.make_opaque(central)
        theme.make_opaque(self._root)

        outer.addWidget(self._root)
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(self._root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._title_bar = TitleBar(self._root)
        self._title_bar.minimizeClicked.connect(self.showMinimized)
        self._title_bar.closeClicked.connect(self._on_close_clicked)
        root_layout.addWidget(self._title_bar)

        body = QWidget(self._root)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 14, 16, 16)
        body_layout.setSpacing(12)
        root_layout.addWidget(body)

        body_layout.addWidget(self._build_status_card(body))
        body_layout.addWidget(self._build_form_card(body))

        # 主按钮
        self._btn_login = QPushButton("登录", body)
        self._btn_login.setObjectName("primaryButton")
        self._btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_login.clicked.connect(self._on_login)
        body_layout.addWidget(self._btn_login)

        # 细进度条（常驻占位，避免布局跳动）
        self._busy = BusyBar(body)
        body_layout.addWidget(self._busy)

        # 操作提示
        self._tip = QLabel(" ", body)
        self._tip.setObjectName("tipLabel")
        self._tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tip.setMinimumHeight(18)
        body_layout.addWidget(self._tip)

        # 底部链接行
        bottom = QHBoxLayout()
        bottom.setSpacing(theme.GAP_XS)
        self._btn_logout = self._link_button("注销", body, self._on_logout, tone="danger")
        self._btn_settings = self._link_button(
            "设置", body, lambda: self.settingsRequested.emit()
        )
        self._btn_logs = self._link_button("日志", body, lambda: self.logsRequested.emit())
        bottom.addStretch()
        bottom.addWidget(self._btn_logout)
        bottom.addWidget(self._btn_settings)
        bottom.addWidget(self._btn_logs)
        bottom.addStretch()
        body_layout.addLayout(bottom)

    def _link_button(self, text: str, parent: QWidget, slot, tone: str = "") -> QPushButton:
        button = QPushButton(text, parent)
        button.setObjectName("linkButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        if tone:
            set_tone(button, tone)
        button.clicked.connect(slot)
        return button

    def _build_status_card(self, parent: QWidget) -> QWidget:
        card = QWidget(parent)
        card.setObjectName("statusCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        self._badge = StatusBadge(52, card)
        layout.addWidget(self._badge, alignment=Qt.AlignmentFlag.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)
        self._status_title = QLabel("正在初始化…", card)
        self._status_title.setObjectName("statusTitle")
        self._status_sub = QLabel("等待网络检测", card)
        self._status_sub.setObjectName("statusSub")
        self._status_time = QLabel("", card)
        self._status_time.setObjectName("statusTime")
        text_layout.addWidget(self._status_title)
        text_layout.addWidget(self._status_sub)
        text_layout.addWidget(self._status_time)
        text_layout.addStretch()
        layout.addLayout(text_layout, 1)

        side_layout = QVBoxLayout()
        side_layout.setSpacing(4)
        self._auto_pill = QLabel("自动登录", card)
        self._auto_pill.setObjectName("statusPill")
        set_tone(self._auto_pill, "primary")
        self._auto_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._countdown_label = QLabel("", card)
        self._countdown_label.setObjectName("statusTime")
        self._countdown_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        side_layout.addWidget(self._auto_pill, alignment=Qt.AlignmentFlag.AlignRight)
        side_layout.addWidget(self._countdown_label, alignment=Qt.AlignmentFlag.AlignRight)
        side_layout.addStretch()
        layout.addLayout(side_layout)

        return card

    def _build_form_card(self, parent: QWidget) -> QWidget:
        card = QWidget(parent)
        card.setObjectName("formCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # 当前网络
        layout.addLayout(self._network_field(card))

        # 学号
        self._user_input = InputFrame(placeholder="请输入学号")
        layout.addLayout(v_field("学号", self._user_input))

        # 密码
        self._pass_input = InputFrame(placeholder="请输入密码", password=True)
        layout.addLayout(v_field("密码", self._pass_input))

        # 学号/密码框回车直接提交
        self._user_input.returnPressed.connect(self._on_login)
        self._pass_input.returnPressed.connect(self._on_login)

        # 服务类型
        self._segment = SegmentedControl([name for name, _ in DEFAULT_CARRIERS], card)
        layout.addLayout(v_field("服务类型", self._segment))

        # 开关行
        switch_row = QHBoxLayout()
        switch_row.setSpacing(theme.GAP_XL)
        self._remember_switch = Switch(card)
        self._remember_switch.setChecked(True)
        self._remember_switch.toggled.connect(lambda _checked: self._sync_auto_login_pill())
        self._bind_switch = Switch(card)
        self._bind_switch.setChecked(True)
        switch_row.addLayout(h_switch_row("记住并自动登录", self._remember_switch))
        switch_row.addLayout(h_switch_row("绑定当前网络", self._bind_switch))
        switch_row.addStretch()
        layout.addLayout(switch_row)

        return card

    def _network_field(self, parent: QWidget) -> QVBoxLayout:
        self._network_combo = ComboBox(parent)
        self._network_combo.currentIndexChanged.connect(self._on_network_changed)

        self._btn_refresh = QPushButton("刷新", parent)
        self._btn_refresh.setObjectName("outlineButton")
        self._btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_refresh.setToolTip("重新识别当前网络")
        self._btn_refresh.clicked.connect(self._on_refresh_clicked)

        row = QHBoxLayout()
        row.setSpacing(theme.GAP_SM)
        row.addWidget(self._network_combo, 1)
        row.addWidget(self._btn_refresh)

        layout = QVBoxLayout()
        layout.setSpacing(theme.GAP_SM)
        layout.addWidget(field_label("当前网络", parent))
        layout.addLayout(row)
        return layout

    # ------------------------------------------------------------------ 数据绑定

    def _connect_daemon(self) -> None:
        self.daemon.statusChanged.connect(self._on_status)
        self.daemon.loginFinished.connect(self._on_login_finished)
        self.daemon.logoutFinished.connect(self._on_logout_finished)
        self.daemon.portalConfig.connect(self._on_portal_config)
        self.daemon.networkChanged.connect(self._on_network_signal)
        self.daemon.heartbeat.connect(self._on_heartbeat)

    def _on_portal_config(self, config) -> None:
        self._carrier_map = dict(config.carriers)
        self._segment.setOptions(config.carrier_names(), keep_current=True)

    def _on_heartbeat(self, delay: float) -> None:
        self._next_poll_ts = time.monotonic() + max(0.0, float(delay))

    def _tick_countdown(self) -> None:
        if self._next_poll_ts is None:
            self._countdown_label.setText("")
            return
        remaining = self._next_poll_ts - time.monotonic()
        if remaining <= 0:
            self._countdown_label.setText("正在检测…")
        else:
            self._countdown_label.setText(f"{int(remaining)}s 后检测")

    def _sync_auto_login_pill(self) -> None:
        enabled = self._remember_switch.isChecked() and bool(
            self.store.option("auto_login", True)
        )
        self._auto_pill.setText("自动登录 开" if enabled else "自动登录 关")
        set_tone(self._auto_pill, "primary" if enabled else "muted")

    # ------------------------------------------------------------------ 网络列表

    def _refresh_networks(self) -> None:
        """渲染网络下拉；只读守护线程缓存，界面线程不执行任何子进程。"""
        self._render_networks(self.daemon.network, force=True)

    def _render_networks(self, current, force: bool = False) -> bool:
        """按网络身份渲染下拉；内容未变化时跳过，避免覆盖用户正在输入的内容。"""
        saved = self.store.saved_networks()
        signature = (
            getattr(current, "kind", ""),
            getattr(current, "id", ""),
            getattr(current, "label", ""),
            tuple(saved),
        )
        if not force and signature == self._network_signature:
            return False
        self._network_signature = signature

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
            self._network_combo.addItem(self._network_label(nid, username, carrier), nid)
            seen.add(nid)

        if not current.connected:
            self._network_combo.addItem("未检测到网络", "")
        self._network_combo.blockSignals(False)
        self._on_network_changed()
        return True

    def _on_refresh_clicked(self) -> None:
        self._set_tip("info", "正在刷新网络…")
        self.daemon.request_refresh_network()

    def _on_network_signal(self, info) -> None:
        if self._render_networks(info):
            self._set_tip("info", f"当前网络：{info.label}")

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

    # ------------------------------------------------------------------ 动作

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
        self._is_busy = busy
        self._btn_login.setEnabled(not busy)
        self._btn_login.setText("正在认证…" if busy else "登录")
        self._btn_logout.setEnabled(not busy)
        self._btn_refresh.setEnabled(not busy)
        self._network_combo.setEnabled(not busy)
        if busy:
            self._busy.start()
        else:
            self._busy.stop()

    def _on_login_finished(self, ok: bool, message: str) -> None:
        self._set_busy(False)
        self._set_tip("success" if ok else "error", message)
        if ok:
            # 绑定关系可能新增，强制重渲染下拉
            self._render_networks(self.daemon.network, force=True)

    def _on_logout_finished(self, ok: bool, message: str) -> None:
        self._set_tip("success" if ok else "error", message)

    def _on_status(self, state: str, message: str, network_label: str) -> None:
        style = theme.state_style(state)
        self._badge.setState(state)
        self._status_title.setText(style.text)
        self._status_sub.setText(f"{network_label} · {message}")

        ts = self.daemon.last_login_ts
        self._status_time.setText(
            f"最近认证：{time.strftime('%m-%d %H:%M:%S', time.localtime(ts))}" if ts else ""
        )

        if state == "logging":
            self._set_busy(True)
            self._set_tip("info", message)
        elif self._is_busy:
            # 守护线程直接切走了状态（例如自动登录失败），这里也要解除加载态
            self._set_busy(False)

    def _set_tip(self, level: str, text: str) -> None:
        self._tip.setProperty("level", level)
        self._tip.setText(text)
        style = self._tip.style()
        style.unpolish(self._tip)
        style.polish(self._tip)

    # ------------------------------------------------------------------ 窗口行为

    def _hide_to_tray(self) -> None:
        self.hide()

    def _on_close_clicked(self) -> None:
        """关闭按钮：按设置决定收进托盘还是退出程序。"""
        if self.store.option("close_to_tray", True):
            self._hide_to_tray()
        else:
            self.quitRequested.emit()

    def closeEvent(self, event) -> None:  # noqa: N802
        # Alt+F4 / 任务栏关闭走同一套策略，避免"设置说退出但窗口只是隐藏"
        if self.store.option("close_to_tray", True):
            event.ignore()
            self._hide_to_tray()
        else:
            event.accept()
            self.quitRequested.emit()

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.daemon.request_refresh_network()
        self._sync_auto_login_pill()
