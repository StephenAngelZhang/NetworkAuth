"""校园网自动登录守护进程入口。

- 单实例运行
- 启动托盘、守护线程与主界面
- 支持 --minimized 开机静默启动
"""

from __future__ import annotations

import argparse
import ctypes
import sys
from typing import Optional

from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from app import icons, theme
from app.log_dialog import LogDialog
from app.main_window import MainWindow
from app.settings_dialog import SettingsDialog
from app.tray import TrayController
from core.config import ConfigStore
from core.daemon import Daemon

APP_ID = "NetworkAuth.CampusAutoLogin.1.0"


def _set_app_user_model_id() -> None:
    """Windows 通知需要显式 AppUserModelID。"""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except OSError:
        pass


def _single_instance_server(app: QApplication) -> Optional[QLocalServer]:
    """若已有实例运行，则通知它显示窗口并返回 None。"""
    name = "NetworkAuthSingleInstance"
    client = QLocalSocket()
    client.connectToServer(name)
    if client.waitForConnected(500):
        client.write(b"show")
        client.flush()
        client.waitForBytesWritten(500)
        return None

    QLocalServer.removeServer(name)
    server = QLocalServer(app)
    if not server.listen(name):
        return None
    return server


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minimized", action="store_true", help="启动时不显示主窗口")
    args = parser.parse_args()

    _set_app_user_model_id()

    app = QApplication(sys.argv)
    app.setApplicationName("校园网自动登录")
    app.setApplicationDisplayName("校园网自动登录")
    app.setWindowIcon(icons.app_icon())
    app.setQuitOnLastWindowClosed(False)
    theme.apply(app)

    server = _single_instance_server(app)
    if server is None:
        return 0

    store = ConfigStore()
    daemon = Daemon(store)
    window = MainWindow(store, daemon)
    tray = TrayController(store, daemon)

    # 托盘菜单动作
    tray.showRequested.connect(window.show_from_tray)
    tray.loginRequested.connect(lambda: daemon.request_login())
    tray.logoutRequested.connect(daemon.request_logout)
    tray.settingsRequested.connect(lambda: _open_settings(window, store, daemon))
    tray.logsRequested.connect(lambda: _open_logs(window, store))
    tray.quitRequested.connect(lambda: _quit(app, daemon))

    # 守护线程状态 -> 托盘与窗口
    daemon.statusChanged.connect(
        lambda state, message, label: tray.set_state(state, f"{label} · {message}")
    )
    daemon.notifyRequested.connect(tray.show_notification)

    # 单实例唤醒
    server.newConnection.connect(lambda: _on_wake(window, server))

    daemon.start()
    if not args.minimized:
        window.show()
    else:
        tray.show_message("校园网自动登录", "已最小化到系统托盘运行")

    return app.exec()


def _on_wake(window: MainWindow, server: QLocalServer) -> None:
    client = server.nextPendingConnection()
    if client is None:
        return
    client.waitForReadyRead(300)
    client.close()
    window.show_from_tray()


def _open_settings(window: MainWindow, store: ConfigStore, daemon: Daemon) -> None:
    dialog = SettingsDialog(store, window)
    if dialog.exec():
        daemon.refresh_portal()


def _open_logs(window: MainWindow, store: ConfigStore) -> None:
    LogDialog(store, window).exec()


def _quit(app: QApplication, daemon: Daemon) -> None:
    daemon.stop()
    daemon.wait(3000)
    app.quit()


if __name__ == "__main__":
    sys.exit(main())
