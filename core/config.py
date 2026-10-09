"""配置与凭据持久化。

存储位置：%APPDATA%\\NetworkAuth\\config.json
密码使用 Windows DPAPI 加密后以 base64 文本落盘。
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, fields
from typing import Any, Optional

from core import credential

APP_NAME = "NetworkAuth"

DEFAULT_BASE = "http://10.2.255.26"

DEFAULT_OPTIONS: dict[str, Any] = {
    "auto_login": True,          # 检测到未认证时自动登录
    "reconnect": True,           # 掉线自动重连
    "notify": True,              # Windows 通知
    "interval": 15,              # 未认证时的检测间隔（秒）
    "interval_online": 60,       # 已认证时的检测间隔（秒）
    "login_method": "GET",       # 门户登录请求方式 GET / POST
    "close_to_tray": True,       # 关闭窗口时最小化到托盘
    "auto_start": False,         # 开机自启（镜像注册表状态）
}

MAX_HISTORY = 300


def app_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_NAME)


def config_path() -> str:
    return os.path.join(app_dir(), "config.json")


def mask_username(username: str) -> str:
    """学号脱敏：中间字符打码。"""
    name = username or ""
    if len(name) <= 4:
        return "*" * len(name)
    keep = 2
    return f"{name[:keep]}{'*' * (len(name) - keep * 2)}{name[-keep:]}"


@dataclass
class Profile:
    """一套账号凭据。"""

    username: str = ""
    password_enc: str = ""
    carrier: str = "校园用户"
    suffix: str = ""
    enabled: bool = True
    updated_at: float = 0.0

    @property
    def password(self) -> str:
        try:
            return credential.unprotect(self.password_enc)
        except OSError:
            return ""

    @password.setter
    def password(self, value: str) -> None:
        self.password_enc = credential.protect(value or "")

    @property
    def valid(self) -> bool:
        return bool(self.username) and bool(self.password)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Profile":
        data = data or {}
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


class ConfigStore:
    """线程安全的配置读写。"""

    GLOBAL_KEY = "__default__"

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or config_path()
        self._lock = threading.RLock()
        self.data: dict[str, Any] = self._default_data()
        self.load()

    # ---------- 基础读写 ----------

    @staticmethod
    def _default_data() -> dict[str, Any]:
        return {
            "version": 1,
            "portal_base": DEFAULT_BASE,
            "options": dict(DEFAULT_OPTIONS),
            "profiles": {},     # network_id -> Profile dict
            "history": [],
        }

    def load(self) -> None:
        with self._lock:
            data = self._default_data()
            try:
                with open(self.path, "r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
            except (OSError, ValueError):
                loaded = {}
            if isinstance(loaded, dict):
                data["portal_base"] = loaded.get("portal_base", DEFAULT_BASE) or DEFAULT_BASE
                options = dict(DEFAULT_OPTIONS)
                stored_options = loaded.get("options") or {}
                if isinstance(stored_options, dict):
                    options.update({k: v for k, v in stored_options.items() if k in DEFAULT_OPTIONS})
                data["options"] = options
                profiles = loaded.get("profiles")
                if isinstance(profiles, dict):
                    data["profiles"] = {
                        str(k): Profile.from_dict(v).to_dict()
                        for k, v in profiles.items()
                        if isinstance(v, dict)
                    }
                history = loaded.get("history")
                if isinstance(history, list):
                    data["history"] = [h for h in history if isinstance(h, dict)][-MAX_HISTORY:]
            self.data = data

    def save(self) -> None:
        with self._lock:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            payload = json.dumps(self.data, ensure_ascii=False, indent=2)
            directory = os.path.dirname(self.path)
            handle = tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=directory, delete=False, suffix=".tmp"
            )
            try:
                with handle:
                    handle.write(payload)
                os.replace(handle.name, self.path)
            except OSError:
                try:
                    os.unlink(handle.name)
                except OSError:
                    pass
                raise

    # ---------- 选项 ----------

    @property
    def options(self) -> dict[str, Any]:
        with self._lock:
            return self.data.setdefault("options", dict(DEFAULT_OPTIONS))

    def option(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self.data.setdefault("options", dict(DEFAULT_OPTIONS)).get(
                key, DEFAULT_OPTIONS.get(key, default)
            )

    def set_option(self, key: str, value: Any) -> None:
        with self._lock:
            self.data.setdefault("options", dict(DEFAULT_OPTIONS))[key] = value
            self.save()

    def set_options(self, values: dict[str, Any]) -> None:
        with self._lock:
            self.data.setdefault("options", dict(DEFAULT_OPTIONS)).update(values)
            self.save()

    @property
    def portal_base(self) -> str:
        with self._lock:
            return self.data.get("portal_base") or DEFAULT_BASE

    @portal_base.setter
    def portal_base(self, value: str) -> None:
        with self._lock:
            self.data["portal_base"] = value or DEFAULT_BASE
            self.save()

    # ---------- 账号 ----------

    def profile_for(self, network_id: str) -> Optional[Profile]:
        """精确取某个网络绑定的账号（不含全局回退）。"""
        if not network_id:
            return None
        with self._lock:
            raw = self.data.setdefault("profiles", {}).get(network_id)
        if not raw:
            return None
        profile = Profile.from_dict(raw)
        return profile if profile.username else None

    def default_profile(self) -> Optional[Profile]:
        return self.profile_for(self.GLOBAL_KEY)

    def resolve(self, network_id: str) -> Optional[Profile]:
        """优先取当前网络绑定的账号，未绑定则回退全局默认账号。"""
        return self.profile_for(network_id) or self.default_profile()

    def set_profile(self, network_id: Optional[str], profile: Profile) -> None:
        with self._lock:
            profile.updated_at = time.time()
            self.data.setdefault("profiles", {})[network_id or self.GLOBAL_KEY] = profile.to_dict()
            self.save()

    def remove_profile(self, network_id: str) -> None:
        with self._lock:
            self.data.setdefault("profiles", {}).pop(network_id, None)
            self.save()

    def saved_networks(self) -> list[tuple[str, str, str]]:
        """返回 [(network_id, 学号, 服务类型)]，不含全局默认。"""
        with self._lock:
            items = list(self.data.setdefault("profiles", {}).items())
        result: list[tuple[str, str, str]] = []
        for network_id, raw in items:
            if network_id == self.GLOBAL_KEY:
                continue
            profile = Profile.from_dict(raw)
            if profile.username:
                result.append((network_id, profile.username, profile.carrier))
        return result

    # ---------- 历史 ----------

    def add_history(self, record: dict[str, Any]) -> None:
        with self._lock:
            record.setdefault("ts", time.time())
            self.data.setdefault("history", []).append(record)
            self.data["history"] = self.data["history"][-MAX_HISTORY:]
            self.save()

    def history(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.data.get("history", []))

    def clear_history(self) -> None:
        with self._lock:
            self.data["history"] = []
            self.save()
