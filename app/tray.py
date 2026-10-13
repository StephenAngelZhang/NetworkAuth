"""系统托盘：图标、菜单、通知。"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from app import icons
from core import autostart
from core.config import ConfigStore
from core.daemon import STATE_ONLINE, Daemon

logger = logging.getLogger("networkauth")


class TrayController(QObject):
    """托盘控制器：本身不显示任何窗口部件，只驱动 QSystemTrayIcon。"""

    showRequested = pyqtSignal()
    loginRequested = pyqtSignal()
    logoutRequested = pyqtSignal()
    settingsRequested = pyqtSignal()
    logsRequested = pyqtSignal()
    quitRequested = pyqtSignal()

    def __init__(
        self,
        store: ConfigStore,
        daemon: Daemon,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.store = store
        self.daemon = daemon
        self._state = "offline"

        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(icons.tray_icon("offline"))
        self._tray.setToolTip("校园网自动登录 · 初始化中")
        self._tray.activated.connect(self._on_activated)

        self._menu = QMenu()
        self._menu.aboutToShow.connect(self._refresh_menu)
        self._build_menu()
        self._tray.setContextMenu(self._menu)
        self._tray.show()

    def _build_menu(self) -> None:
        self._actions: dict[str, QAction] = {}

        # 顶部显示当前状态（不可点击），让托盘菜单自带状态反馈
        self._status_action = QAction("初始化中", self)
        self._status_action.setEnabled(False)
        self._menu.addAction(self._status_action)
        self._menu.addSeparator()

        def add(key: str, text: str, slot) -> QAction:
            action = QAction(text, self)
            action.triggered.connect(slot)
            self._menu.addAction(action)
            self._actions[key] = action
            return action

        add("show", "打开主界面", self.showRequested.emit)
        self._menu.addSeparator()
        add("login", "立即登录", self.loginRequested.emit)
        add("logout", "注销", self.logoutRequested.emit)
        self._menu.addSeparator()
        add("settings", "设置", self.settingsRequested.emit)
        add("logs", "查看日志", self.logsRequested.emit)
        self._menu.addSeparator()
        auto = QAction("开机自启", self, checkable=True)
        auto.triggered.connect(self._toggle_autostart)
        self._menu.addAction(auto)
        self._actions["autostart"] = auto
        self._menu.addSeparator()
        add("quit", "退出", self.quitRequested.emit)

    def _refresh_menu(self) -> None:
        """按当前状态置灰无意义的菜单项。"""
        online = self._state == STATE_ONLINE
        if "login" in self._actions:
            self._actions["login"].setEnabled(not online)
        if "logout" in self._actions:
            self._actions["logout"].setEnabled(online)
        if "autostart" in self._actions:
            self._actions["autostart"].blockSignals(True)
            self._actions["autostart"].setChecked(autostart.is_enabled())
            self._actions["autostart"].blockSignals(False)

    def _toggle_autostart(self, checked: bool) -> None:
        # QAction 自带的勾选状态可能是错的，必须按注册表实际结果回滚
        ok, reason = autostart.set_enabled(checked)
        if ok:
            self.store.set_option("auto_start", checked)
            logger.info("开机自启已%s", "开启" if checked else "关闭")
            return

        logger.warning("设置开机自启失败：%s", reason)
        action = self._actions.get("autostart")
        if action is not None:
            action.blockSignals(True)
            action.setChecked(autostart.is_enabled())
            action.blockSignals(False)
        self.show_notification("校园网自动登录", f"开机自启设置失败：{reason}", ok=False)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.showRequested.emit()

    def set_state(self, state: str, tooltip: str = "") -> None:
        self._state = state
        self._tray.setIcon(icons.tray_icon(state))
        self._tray.setToolTip(tooltip or f"校园网自动登录 · {state}")
        self._status_action.setText(tooltip or state)

    def show_notification(self, title: str, message: str, ok: bool = True) -> None:
        icon = (
            QSystemTrayIcon.MessageIcon.Information
            if ok
            else QSystemTrayIcon.MessageIcon.Warning
        )
        self._tray.showMessage(title, message, icon, 3500)

    def show_message(self, title: str, message: str) -> None:
        self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 2500)
