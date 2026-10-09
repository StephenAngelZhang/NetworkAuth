"""守护线程：网络/认证状态检测、自动登录、掉线重连与通知。

所有网络 IO 都在该 QThread 内执行，通过信号回传 UI，避免界面卡死。
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from core import network as net
from core.config import ConfigStore, Profile, mask_username
from core.portal import PortalClient, DEFAULT_CARRIERS

# 状态
STATE_NO_NETWORK = "no_network"
STATE_OFFLINE = "offline"
STATE_ONLINE = "online"
STATE_NEED_LOGIN = "need_login"
STATE_NO_CREDENTIAL = "no_credential"
STATE_LOGGING = "logging"
STATE_FAILED = "failed"
STATE_CRED_ERROR = "credential_error"

STATE_TEXT = {
    STATE_NO_NETWORK: "未连接网络",
    STATE_OFFLINE: "非校园网",
    STATE_ONLINE: "已连接",
    STATE_NEED_LOGIN: "待认证",
    STATE_NO_CREDENTIAL: "未保存账号",
    STATE_LOGGING: "认证中",
    STATE_FAILED: "认证失败",
    STATE_CRED_ERROR: "账号异常",
}

# 判定为账号本身有问题时停止自动重试，避免被锁号
_CREDENTIAL_ERROR_HINTS = (
    "密码错误",
    "用户名或密码错误",
    "账号或密码错误",
    "账号密码错误",
    "不存在",
    "已停用",
    "已禁用",
    "已锁定",
    "已过期",
    "欠费",
)

_MIN_DELAY = 5
_MAX_DELAY = 300


class Daemon(QThread):
    """后台守护循环。"""

    statusChanged = pyqtSignal(str, str, str)          # state, message, network_label
    historyRecorded = pyqtSignal(dict)
    notifyRequested = pyqtSignal(str, str, bool)       # title, message, ok
    loginFinished = pyqtSignal(bool, str)
    logoutFinished = pyqtSignal(bool, str)
    portalConfig = pyqtSignal(object)                  # PortalConfig

    def __init__(self, store: ConfigStore, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self._stop_event = threading.Event()
        self._wakeup = threading.Event()
        self._lock = threading.Lock()
        self._actions: list[dict] = []
        self._client: Optional[PortalClient] = None
        self._fail_count = 0
        self._blocked = False
        self._delay = float(store.option("interval", 15))
        self._state = STATE_NO_NETWORK
        self._message = ""
        self._network = net.NetworkInfo(net.NONE, "", "无网络")
        self._last_login_ts: Optional[float] = None
        self._carriers: list[tuple[str, str]] = list(DEFAULT_CARRIERS)

    # ---------- 对外状态 ----------

    @property
    def state(self) -> str:
        return self._state

    @property
    def message(self) -> str:
        return self._message

    @property
    def network(self) -> net.NetworkInfo:
        return self._network

    @property
    def last_login_ts(self) -> Optional[float]:
        return self._last_login_ts

    def carriers(self) -> list[tuple[str, str]]:
        return list(self._carriers)

    @property
    def client(self) -> PortalClient:
        base = self.store.portal_base
        method = str(self.store.option("login_method", "GET")).upper()
        if self._client is None or self._client.base != base or self._client.method != method:
            self._client = PortalClient(base=base, method=method)
        return self._client

    # ---------- 请求 ----------

    def request_login(
        self,
        profile: Optional[Profile] = None,
        bind_to: Optional[str] = None,
        save: bool = False,
    ) -> None:
        """请求登录。profile 为空时使用已保存账号；save=True 时成功后写入配置。"""
        with self._lock:
            self._actions.append(
                {"type": "login", "profile": profile, "bind": bind_to, "save": save}
            )
        self._wakeup.set()

    def request_logout(self) -> None:
        with self._lock:
            self._actions.append({"type": "logout"})
        self._wakeup.set()

    def refresh_portal(self) -> None:
        with self._lock:
            self._actions.append({"type": "refresh"})
        self._wakeup.set()

    def unblock(self) -> None:
        """清除账号异常导致的暂停状态。"""
        self._blocked = False
        self._fail_count = 0
        self._wakeup.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._wakeup.set()

    # ---------- 主循环 ----------

    def run(self) -> None:  # pragma: no cover - 线程主循环
        self.refresh_portal()
        while not self._stop_event.is_set():
            self._wakeup.clear()
            try:
                self._tick()
            except Exception as exc:  # 保证守护线程不因异常退出
                self._set_state(STATE_OFFLINE, f"检测异常：{type(exc).__name__}")
            self._sleep(self._delay)

    def _sleep(self, seconds: float) -> None:
        deadline = time.time() + max(1.0, float(seconds))
        while time.time() < deadline:
            if self._stop_event.is_set() or self._wakeup.is_set():
                return
            time.sleep(min(0.25, max(0.05, deadline - time.time())))

    def _tick(self) -> None:
        self._handle_actions()

        info = net.current_network()
        self._network = info

        if info.kind == net.NONE:
            self._set_state(STATE_NO_NETWORK, "未检测到网络连接")
            self._delay = self._interval(False)
            return

        base = self.store.portal_base
        if not net.portal_reachable(base):
            self._set_state(STATE_OFFLINE, "当前网络不是校园网，或认证服务器不可达")
            self._delay = self._interval(False)
            return

        if net.internet_reachable():
            self._fail_count = 0
            self._set_state(STATE_ONLINE, "已通过认证，可正常上网")
            self._delay = self._interval(True)
            return

        self._set_state(STATE_NEED_LOGIN, "校园网已连接，需要认证")
        if not self.store.option("auto_login", True):
            self._delay = self._interval(False)
            return

        if self._blocked:
            self._set_state(STATE_CRED_ERROR, "账号被门户拒绝，已停止自动重试")
            self._delay = self._interval(False)
            return

        profile = self.store.resolve(info.id)
        if profile is None or not profile.valid or not profile.enabled:
            self._set_state(STATE_NO_CREDENTIAL, "当前网络尚未保存可用账号")
            self._delay = self._interval(False)
            return

        self._do_login(info, profile, bind_to=None, save=False)

    # ---------- 动作 ----------

    def _handle_actions(self) -> None:
        with self._lock:
            actions = self._actions
            self._actions = []
        if not actions:
            return

        info = net.current_network()
        self._network = info

        for action in actions:
            kind = action.get("type")
            if kind == "refresh":
                self._discover()
                continue
            if kind == "logout":
                ok = self.client.logout()
                self.logoutFinished.emit(ok, "已发送注销请求" if ok else "注销失败，请检查网络")
                self._delay = 2.0
                continue
            if kind != "login":
                continue

            profile: Optional[Profile] = action.get("profile")
            bind_to: Optional[str] = action.get("bind")
            save: bool = bool(action.get("save"))
            if profile is None:
                profile = self.store.resolve(info.id or net.ETHERNET_ID)
            if profile is None or not profile.valid:
                self.loginFinished.emit(False, "请先填写学号与密码")
                self._delay = self._interval(False)
                continue
            self._blocked = False
            self._do_login(info, profile, bind_to=bind_to, save=save)

    def _discover(self) -> None:
        config = self.client.discover(force=True)
        if config.carriers:
            self._carriers = list(config.carriers)
        self.portalConfig.emit(config)

    # ---------- 登录 ----------

    def _do_login(
        self,
        info: net.NetworkInfo,
        profile: Profile,
        bind_to: Optional[str],
        save: bool,
    ) -> None:
        self._set_state(STATE_LOGGING, f"正在认证 {mask_username(profile.username)}…")

        result = self.client.login(profile.username, profile.password, profile.suffix)
        time.sleep(2.5)                      # 等待门户上线生效
        online = net.internet_reachable()

        if online:
            ok = True
            message = "登录成功" if result.verdict != "fail" else f"{result.message}（当前已可上网）"
        elif result.verdict == "success":
            ok = True
            message = "门户已接受登录（外网探测未确认）"
        else:
            ok = False
            message = result.message or "认证未生效"

        record = {
            "ts": time.time(),
            "network": info.label,
            "network_id": info.id,
            "username": mask_username(profile.username),
            "carrier": profile.carrier,
            "ok": ok,
            "verdict": result.verdict,
            "message": message,
            "request": result.request,
            "detail": result.detail,
        }
        self.store.add_history(record)
        self.historyRecorded.emit(record)

        if ok:
            self._fail_count = 0
            self._last_login_ts = record["ts"]
            self._set_state(STATE_ONLINE, message)
            self._delay = self._interval(True)
            if save:
                self.store.set_profile(bind_to, profile)
        else:
            self._set_state(STATE_FAILED, message)
            if any(hint in message for hint in _CREDENTIAL_ERROR_HINTS):
                self._blocked = True
                self._set_state(STATE_CRED_ERROR, f"{message}，已停止自动重试")
            if self.store.option("reconnect", True) and not self._blocked:
                self._fail_count += 1
                self._delay = min(
                    max(_MIN_DELAY, self._interval(False)) * (2 ** min(self._fail_count, 5)),
                    _MAX_DELAY,
                )
            else:
                self._delay = self._interval(False)

        if self.store.option("notify", True):
            title = "校园网自动登录"
            text = f"{info.label} · {message}"
            self.notifyRequested.emit(title, text, ok)

        self.loginFinished.emit(ok, message)

    # ---------- 工具 ----------

    def _interval(self, online: bool) -> float:
        key = "interval_online" if online else "interval"
        return float(self.store.option(key, 60 if online else 15))

    def _set_state(self, state: str, message: str) -> None:
        if state == self._state and message == self._message:
            return
        self._state = state
        self._message = message
        self.statusChanged.emit(state, message, self._network.label)
