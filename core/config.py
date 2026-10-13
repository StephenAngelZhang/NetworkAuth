"""配置与凭据持久化。

存储位置：%APPDATA%\\NetworkAuth\\config.json
密码使用 Windows DPAPI 加密后以 base64 文本落盘。
"""

from __future__ import annotations

import binascii
import json
import logging
import os
import shutil
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, fields
from typing import Any, Optional

from core import credential

logger = logging.getLogger("networkauth")

APP_NAME = "NetworkAuth"

DEFAULT_BASE = "http://10.2.255.26"

# 配置结构版本，便于后续迁移
CURRENT_VERSION = 2

DEFAULT_OPTIONS: dict[str, Any] = {
    "auto_login": True,          # 检测到未认证时自动登录
    "reconnect": True,           # 掉线自动重连
    "notify": True,              # Windows 通知
    "interval": 15,              # 未认证时的检测间隔（秒）
    "interval_online": 60,       # 已认证时的检测间隔（秒）
    "close_to_tray": True,       # 关闭窗口时最小化到托盘
    "auto_start": False,         # 开机自启（镜像注册表状态）
}
# 注：门户登录固定使用 GET（该门户对 POST 返回"无法获取用户认证账号"），
# 因此不再提供"请求方式"选项。

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
        # 配置被外部修改/换 Windows 用户时可能解不开，这里一律降级为空串，
        # 避免 binascii.Error / UnicodeDecodeError 直接冒到界面线程。
        try:
            return credential.unprotect(self.password_enc)
        except (OSError, ValueError, binascii.Error, UnicodeDecodeError):
            logger.warning("凭据解密失败，已按空密码处理")
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

    def backup_path(self) -> str:
        return self.path + ".bak"

    @staticmethod
    def _read_json(path: str) -> tuple[dict[str, Any], bool]:
        """读取 JSON，返回 (内容, 是否损坏)。文件不存在视为未损坏的空配置。"""
        if not os.path.exists(path):
            return {}, False
        try:
            with open(path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        except (OSError, ValueError) as exc:
            logger.error("配置文件无法解析：%s（%s）", path, exc)
            return {}, True
        if not isinstance(loaded, dict):
            logger.error("配置文件结构异常（顶层不是对象）：%s", path)
            return {}, True
        return loaded, False

    def _quarantine(self) -> str:
        """把损坏的配置改名留档，避免直接覆盖丢失现场。"""
        target = f"{self.path}.broken-{time.strftime('%Y%m%d-%H%M%S')}"
        try:
            os.replace(self.path, target)
            logger.warning("损坏的配置已留档：%s", target)
            return target
        except OSError as exc:
            logger.error("无法留档损坏的配置：%s", exc)
            return ""

    def load(self) -> None:
        with self._lock:
            loaded, damaged = self._read_json(self.path)
            if damaged:
                self._quarantine()
                restored, restore_damaged = self._read_json(self.backup_path())
                if restored and not restore_damaged:
                    logger.warning("已从备份恢复配置：%s", self.backup_path())
                    loaded = restored
                else:
                    logger.error("没有可用备份，配置已重置为默认值")

            data = self._default_data()
            data["portal_base"] = str(loaded.get("portal_base") or DEFAULT_BASE)

            options = dict(DEFAULT_OPTIONS)
            stored_options = loaded.get("options")
            if isinstance(stored_options, dict):
                options.update({k: v for k, v in stored_options.items() if k in DEFAULT_OPTIONS})
            data["options"] = options

            profiles = loaded.get("profiles")
            if isinstance(profiles, dict):
                data["profiles"] = {
                    str(key): Profile.from_dict(value).to_dict()
                    for key, value in profiles.items()
                    if isinstance(value, dict)
                }

            history = loaded.get("history")
            if isinstance(history, list):
                data["history"] = [item for item in history if isinstance(item, dict)][-MAX_HISTORY:]

            data["version"] = self._migrate(loaded.get("version"))
            self.data = data

    @staticmethod
    def _migrate(stored_version: Any) -> int:
        """把旧结构版本标记为当前版本（字段级兼容由上面的解析逻辑兜底）。"""
        try:
            version = int(stored_version or 1)
        except (TypeError, ValueError):
            version = 1
        if version != CURRENT_VERSION:
            logger.info("配置版本 %s -> %s", version, CURRENT_VERSION)
        return CURRENT_VERSION

    def save(self) -> None:
        with self._lock:
            directory = os.path.dirname(self.path)
            os.makedirs(directory, exist_ok=True)
            payload = json.dumps(self.data, ensure_ascii=False, indent=2)
            handle = tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=directory, delete=False, suffix=".tmp"
            )
            try:
                with handle:
                    handle.write(payload)
                self._refresh_backup()
                os.replace(handle.name, self.path)
            except OSError:
                try:
                    os.unlink(handle.name)
                except OSError:
                    pass
                raise

    def _refresh_backup(self) -> None:
        """保留上一份可用配置作为备份，供损坏时恢复。"""
        if not os.path.exists(self.path):
            return
        try:
            shutil.copy2(self.path, self.backup_path())
        except OSError as exc:
            logger.warning("备份配置失败：%s", exc)

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
