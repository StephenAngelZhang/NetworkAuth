"""校园网自动登录守护进程入口。

- 单实例运行：Windows 命名互斥体判定唯一性，避免单文件 exe 首次解包慢
  导致的"两个实例同时常驻"竞态；QLocalSocket 只负责唤醒已有窗口
- 启动托盘、守护线程与主界面
- 支持 --minimized 开机静默启动
- 全局异常捕获 + 轮转文件日志（%APPDATA%\\NetworkAuth\\app.log）
"""

from __future__ import annotations

import argparse
import ctypes
import sys
import time
from typing import Optional

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QWidget

from app import icons, theme
from app.log_dialog import LogDialog
from app.main_window import MainWindow
from app.settings_dialog import SettingsDialog
from app.tray import TrayController
from core import logging_setup
from core.config import ConfigStore
from core.daemon import Daemon

APP_ID = "NetworkAuth.CampusAutoLogin.1.0"
APP_VERSION = "1.1.0"

INSTANCE_SERVER_NAME = "NetworkAuthSingleInstance"
INSTANCE_MUTEX_NAME = "Global\\NetworkAuth.CampusAutoLogin.SingleInstance"
_ERROR_ALREADY_EXISTS = 183

# 互斥体句柄必须保留到进程结束，否则会被 GC 释放导致单实例失效
_instance_handle: Optional[int] = None
_early_errors: list[str] = []
_services: dict[str, object] = {}

logger = logging_setup.logger


def _set_app_user_model_id() -> None:
    """Windows 通知需要显式 AppUserModelID。"""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except OSError:
        pass


def _report_error(summary: str) -> None:
    """异常回调：托盘就绪后弹通知，否则先排队，等托盘建好再补发。"""
    tray = _services.get("tray")
    if tray is None:
        _early_errors.append(summary)
        return
    try:
        tray.show_notification("校园网自动登录 · 运行异常", summary, ok=False)  # type: ignore[attr-defined]
    except Exception:  # 通知失败不能再抛，否则形成递归
        _early_errors.append(summary)


# --------------------------------------------------------------------------- 单实例


def _acquire_instance_lock() -> bool:
    """创建命名互斥体，返回 True 表示本进程是唯一实例。

    内核对象是瞬时且原子的，不存在 QLocalSocket 那种"对方还没开始监听"的超时窗口。
    """
    global _instance_handle

    if sys.platform != "win32":
        return True
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.CreateMutexW(None, True, INSTANCE_MUTEX_NAME)
    except (OSError, AttributeError):
        return True  # 判定不可用时退回 QLocalSocket 行为，不阻断启动

    if not handle:
        logger.warning("创建单实例互斥体失败，退回端口监听判定")
        return True

    if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return False

    _instance_handle = handle
    return True


def _notify_existing(timeout_ms: int = 1500) -> bool:
    """在超时内重试连接已有实例并发送 show 指令。"""
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        client = QLocalSocket()
        client.connectToServer(INSTANCE_SERVER_NAME)
        if client.waitForConnected(300):
            client.write(b"show")
            client.flush()
            client.waitForBytesWritten(300)
            client.disconnectFromServer()
            return True
        client.abort()
    return False


def _create_server(app: QApplication) -> Optional[QLocalServer]:
    """监听唤醒端口；只在监听失败后才清理残留，绝不主动抢占运行中实例。"""
    server = QLocalServer(app)
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if server.listen(INSTANCE_SERVER_NAME):
        return server

    logger.warning("唤醒端口被占用，尝试清理残留后重试")
    QLocalServer.removeServer(INSTANCE_SERVER_NAME)
    if server.listen(INSTANCE_SERVER_NAME):
        return server
    logger.error("无法监听唤醒端口，其他实例将无法唤起本窗口")
    return None


# --------------------------------------------------------------------------- 装配


def _center_on_screen(widget: QWidget) -> None:
    """把窗口摆到主屏可用区域中央。"""
    screen = QGuiApplication.primaryScreen()
    if screen is None or widget is None:
        return
    geometry = screen.availableGeometry()
    frame = widget.frameGeometry()
    frame.moveCenter(geometry.center())
    widget.move(frame.topLeft())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minimized", action="store_true", help="启动时不显示主窗口")
    args = parser.parse_args()

    log_file = logging_setup.setup(on_error=_report_error)
    logger.info("==== 启动 v%s（minimized=%s）日志：%s ====", APP_VERSION, args.minimized, log_file)

    _set_app_user_model_id()

    app = QApplication(sys.argv)
    app.setApplicationName("校园网自动登录")
    app.setApplicationDisplayName("校园网自动登录")
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(icons.app_icon())
    app.setQuitOnLastWindowClosed(False)
    theme.apply(app)

    if not _acquire_instance_lock():
        logger.info("检测到已有实例运行，通知其显示窗口后退出")
        if not _notify_existing():
            logger.warning("未能唤起已有实例窗口（可能仍在初始化）")
        return 0

    server = _create_server(app)

    store = ConfigStore()
    daemon = Daemon(store)
    window = MainWindow(store, daemon)
    tray = TrayController(store, daemon)

    _services["tray"] = tray
    for summary in _early_errors:
        tray.show_notification("校园网自动登录 · 启动异常", summary, ok=False)
    _early_errors.clear()

    # 托盘菜单动作
    tray.showRequested.connect(window.show_from_tray)
    tray.loginRequested.connect(lambda: daemon.request_login())
    tray.logoutRequested.connect(daemon.request_logout)
    tray.settingsRequested.connect(lambda: _open_settings(window, store, daemon))
    tray.logsRequested.connect(lambda: _open_logs(window, store))
    tray.quitRequested.connect(lambda: _quit(app, daemon))
    window.quitRequested.connect(lambda: _quit(app, daemon))

    # 守护线程状态 -> 托盘与窗口
    daemon.statusChanged.connect(
        lambda state, message, label: tray.set_state(state, f"{label} · {message}")
    )
    daemon.notifyRequested.connect(tray.show_notification)

    # 单实例唤醒
    if server is not None:
        server.newConnection.connect(lambda: _on_wake(window, server))

    daemon.start()
    _center_on_screen(window)
    if args.minimized:
        tray.show_message("校园网自动登录", "已最小化到系统托盘运行")
    else:
        window.show()

    exit_code = app.exec()
    logger.info("==== 退出，返回码 %s ====", exit_code)
    return exit_code


def _on_wake(window: MainWindow, server: QLocalServer) -> None:
    """已有实例收到唤醒指令：读取并释放连接，然后显示窗口。"""
    while server.hasPendingConnections():
        client = server.nextPendingConnection()
        if client is None:
            break
        client.waitForReadyRead(300)
        client.readAll()
        client.disconnectFromServer()
        client.deleteLater()
    logger.debug("收到唤醒请求，显示主窗口")
    window.show_from_tray()


def _open_settings(window: MainWindow, store: ConfigStore, daemon: Daemon) -> None:
    dialog = SettingsDialog(store, window)
    if dialog.exec():
        daemon.refresh_portal()


def _open_logs(window: MainWindow, store: ConfigStore) -> None:
    LogDialog(store, window).exec()


def _quit(app: QApplication, daemon: Daemon) -> None:
    logger.info("收到退出请求")
    daemon.stop()
    if not daemon.wait(3000):
        logger.warning("守护线程未在 3 秒内结束")
    app.quit()


if __name__ == "__main__":
    sys.exit(main())
