"""系统托盘：图标、菜单、通知。"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from app import icons
from core import autostart
from core.config import ConfigStore
from core.daemon import Daemon


class TrayController(QWidget):
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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.store = store
        self.daemon = daemon

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
        if "autostart" in self._actions:
            self._actions["autostart"].setChecked(autostart.is_enabled())

    def _toggle_autostart(self, checked: bool) -> None:
        autostart.set_enabled(checked)
        self.store.set_option("auto_start", checked)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.showRequested.emit()

    def set_state(self, state: str, tooltip: str = "") -> None:
        self._tray.setIcon(icons.tray_icon(state))
        text = tooltip or f"校园网自动登录 · {state}"
        self._tray.setToolTip(text)

    def show_notification(self, title: str, message: str, ok: bool = True) -> None:
        icon = (
            QSystemTrayIcon.MessageIcon.Information
            if ok
            else QSystemTrayIcon.MessageIcon.Warning
        )
        self._tray.showMessage(title, message, icon, 3500)

    def show_message(self, title: str, message: str) -> None:
        self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 2500)
