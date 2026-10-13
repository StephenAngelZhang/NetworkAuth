"""守护线程：网络/认证状态检测、自动登录、掉线重连与通知。

所有网络 IO 都在该 QThread 内执行，通过信号回传 UI，避免界面卡死。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from core import network as net
from core.config import ConfigStore, Profile, mask_username
from core.portal import PortalClient, DEFAULT_CARRIERS

logger = logging.getLogger("networkauth")

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

# 登录后等待门户生效：轮询而非固定 sleep，保证注销/手动登录等动作能及时被处理
_VERIFY_TIMEOUT = 3.0
_VERIFY_STEP = 0.25


class Daemon(QThread):
    """后台守护循环。"""

    statusChanged = pyqtSignal(str, str, str)          # state, message, network_label
    historyRecorded = pyqtSignal(dict)
    notifyRequested = pyqtSignal(str, str, bool)       # title, message, ok
    loginFinished = pyqtSignal(bool, str)
    logoutFinished = pyqtSignal(bool, str)
    portalConfig = pyqtSignal(object)                  # PortalConfig
    networkChanged = pyqtSignal(object)                # net.NetworkInfo
    heartbeat = pyqtSignal(float)                      # 每轮检测结束，参数为下轮间隔（秒）

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
    def next_interval(self) -> float:
        """下一次状态检测的间隔（秒），供界面显示倒计时。"""
        return float(self._delay)

    @property
    def client(self) -> PortalClient:
        """门户客户端（按门户地址缓存；登录固定走 GET）。"""
        base = self.store.portal_base
        if self._client is None or self._client.base != base:
            self._client = PortalClient(base=base)
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

    def request_refresh_network(self) -> None:
        """请求在子线程重新识别网络（界面线程本身不跑子进程）。"""
        with self._lock:
            self._actions.append({"type": "network"})
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
                logger.exception("守护循环发生异常")
                self._set_state(STATE_OFFLINE, f"检测异常：{type(exc).__name__}")
            self.heartbeat.emit(float(self._delay))
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
        self._set_network(info)

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
        self._set_network(info)

        for action in actions:
            kind = action.get("type")
            if kind == "refresh":
                self._discover()
                continue
            if kind == "network":
                net.invalidate_network_cache()
                self._set_network(net.current_network(ttl=0), force=True)
                continue
            if kind == "logout":
                self._do_logout(info)
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

    def _do_logout(self, info: net.NetworkInfo) -> None:
        """注销当前网络上的账号；结果写入日志便于对照门户返回。"""
        profile = self.store.resolve(info.id or net.ETHERNET_ID)
        ok = self.client.logout(
            profile.username if profile else "",
            profile.password if profile else "",
            profile.suffix if profile else "",
        )
        who = mask_username(profile.username) if profile else "未知账号"
        if ok:
            logger.info("注销请求已受理（%s）", who)
            message = "已发送注销请求"
        else:
            logger.warning("注销请求未确认（%s）", who)
            message = "注销未生效，请检查网络或在门户页面手动注销"
        self.logoutFinished.emit(ok, message)
        self._delay = 2.0

    def _discover(self) -> None:
        config = self.client.discover(force=True)
        if config.carriers:
            self._carriers = list(config.carriers)
        logger.info(
            "门户配置：endpoint=%s program=%s page=%s login_method=%s en_md5=%s discovered=%s",
            config.api_base(),
            config.program_index,
            config.page_index,
            config.login_method,
            config.en_md5,
            config.discovered,
        )
        self.portalConfig.emit(config)

    # ---------- 登录 ----------

    def _do_login(
        self,
        info: net.NetworkInfo,
        profile: Profile,
        bind_to: Optional[str],
        save: bool,
    ) -> None:
        who = mask_username(profile.username)
        self._set_state(STATE_LOGGING, f"正在认证 {who}…")
        logger.info("开始认证 %s（网络 %s，绑定 %s）", who, info.label, bind_to or "全局默认")

        result = self.client.login(profile.username, profile.password, profile.suffix)
        online = self._wait_online()          # 可被打断的轮询，替代固定 sleep(2.5)

        if online:
            ok = True
            message = "登录成功" if result.verdict != "fail" else f"{result.message}（当前已可上网）"
        elif result.ok:
            ok = True
            message = "门户已接受登录（外网探测未确认）"
        else:
            ok = False
            message = result.message or "认证未生效"
        logger.info("认证结束 ok=%s verdict=%s message=%s", ok, result.verdict, message)

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

    def _wait_online(self) -> bool:
        """轮询外网连通性确认认证是否生效（最多约 3 秒）。

        与固定 ``sleep`` 的区别：一旦有新的动作请求或收到停止信号就立即返回，
        不会把注销 / 手动登录堵在动作队列里。
        """
        deadline = time.monotonic() + _VERIFY_TIMEOUT
        while True:
            if net.internet_reachable(timeout=1.5):
                return True
            if self._stop_event.is_set() or self._wakeup.is_set():
                return False
            if time.monotonic() >= deadline:
                return False
            time.sleep(_VERIFY_STEP)

    def _set_network(self, info: net.NetworkInfo, force: bool = False) -> bool:
        """更新网络身份；发生变化（或 force）时通过信号通知界面。"""
        previous = self._network
        changed = (info.kind, info.id, info.label) != (previous.kind, previous.id, previous.label)
        self._network = info
        if changed:
            logger.info("网络变化：%s -> %s", previous.label, info.label)
        if changed or force:
            self.networkChanged.emit(info)
        return changed

    def _interval(self, online: bool) -> float:
        key = "interval_online" if online else "interval"
        return float(self.store.option(key, 60 if online else 15))

    def _set_state(self, state: str, message: str) -> None:
        if state == self._state and message == self._message:
            return
        self._state = state
        self._message = message
        logger.debug("状态 -> %s：%s", state, message)
        self.statusChanged.emit(state, message, self._network.label)
