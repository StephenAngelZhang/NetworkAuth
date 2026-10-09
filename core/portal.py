"""Dr.COM / EPortal 门户认证客户端。

协议说明（在本校门户实测确认，2026-10）：

- 门户首页 `http://10.2.255.26/` 仍下发旧版 Dr.COM 配置（`authloginport=801`、
  `authloginpath=/eportal/?c=ACSetting&a=Login`），但该地址现在由 nginx+PHP 返回一个
  Vue 单页应用外壳（`<title>EPortal</title>`），**旧 ACSetting 协议已失效**。
- 真实接口在门户前端 JS（a41.js）中定义为 `page.portal_api`：
      http://<host>:<ep_port>/eportal/portal/
  其中 `ep_port` 默认 801。相关端点：
      page/loadConfig        页面与认证参数配置
      login                  认证登录
      online_list / perceive 在线状态、MAC 感知
- 登录为 **GET**，关键参数为 `user_account` / `user_password`，返回 JSONP：
      jsonpReturn({"result":1,"msg":"...","ret_code":""})
  `result=1` 为成功；`ret_code=2` 且 msg 含"已经在线"表示本 IP 已处于认证状态。
- `en_md5=0` 表示密码明文传输（未启用 MD5）。

本模块不硬编码门户版本：启动时调用 `page/loadConfig` 拉取 program_index /
page_index / login_method 等参数，失败时回退实测默认值。
"""

from __future__ import annotations

import hashlib
import json
import re
import socket
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote

import requests

from core.network import decode_best

DEFAULT_BASE = "http://10.2.255.26"
DEFAULT_EPORTAL_PORT = 801
API_PATH = "/eportal/portal/"

DEFAULT_PROGRAM_INDEX = "AYt7X51627897519"
DEFAULT_PAGE_INDEX = "XG7Ubl1627955572"
JS_VERSION = "a41"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 服务类型（校园用户/电信/联通/其他）与账号后缀
DEFAULT_CARRIERS: list[tuple[str, str]] = [
    ("校园用户", ""),
    ("校园电信", "@dx"),
    ("校园联通", "@lt"),
    ("校园其他", ""),
]

_SUCCESS_WORDS = ("成功", "认证成功", "登录成功")
_ALREADY_ONLINE_WORDS = ("已经在线", "已在线", "已认证")
_LOGOUT_SUCCESS_WORDS = ("成功", "下线", "注销成功")


@dataclass
class PortalConfig:
    """门户参数（带实测默认值）。"""

    base: str = DEFAULT_BASE
    eportal_port: int = DEFAULT_EPORTAL_PORT
    api_path: str = API_PATH
    user_field: str = "user_account"
    pass_field: str = "user_password"
    program_index: str = DEFAULT_PROGRAM_INDEX
    page_index: str = DEFAULT_PAGE_INDEX
    login_method: str = "1"
    account_suffix: str = ""
    en_md5: bool = False
    carriers: list[tuple[str, str]] = field(default_factory=lambda: list(DEFAULT_CARRIERS))
    discovered: bool = False

    def api_base(self) -> str:
        host = self.base.rstrip("/")
        if self.eportal_port and self.eportal_port != 80:
            host = f"{host}:{self.eportal_port}"
        path = self.api_path if self.api_path.endswith("/") else self.api_path + "/"
        return host + path

    def carrier_names(self) -> list[str]:
        return [name for name, _ in self.carriers]

    def suffix_of(self, name: str) -> str:
        for carrier_name, suffix in self.carriers:
            if carrier_name == name:
                return suffix
        return ""


@dataclass
class LoginResult:
    ok: bool
    verdict: str          # success / already_online / fail / unknown
    message: str
    status: int = 0
    request: str = ""     # 已脱敏的请求行
    detail: str = ""      # 已脱敏的响应片段

    def __bool__(self) -> bool:
        return self.ok


def local_ip() -> str:
    """取本机访问门户所用网卡的 IPv4（UDP connect 不发包）。"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect((socket.gethostbyname("10.2.255.26"), 80))
            return sock.getsockname()[0]
        finally:
            sock.close()
    except OSError:
        return ""


def local_mac() -> str:
    """取本机 MAC（门户前端使用大写、无分隔符的 12 位十六进制）。"""
    try:
        node = uuid.getnode()
        if (node >> 40) & 1:  # 随机生成的临时地址
            return ""
        return "".join(f"{(node >> shift) & 0xff:02X}" for shift in range(40, -1, -8))
    except Exception:
        return ""


def parse_jsonp(text: str) -> Optional[dict]:
    """解析 `jsonpReturn({...});` 形式的响应。"""
    stripped = (text or "").strip()
    match = re.search(r"\(\s*(\{.*\})\s*\)\s*;?\s*$", stripped, re.S)
    raw = match.group(1) if match else stripped
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


class PortalClient:
    """门户登录 / 注销客户端。"""

    CACHE_TTL = 600.0

    def __init__(self, base: str = DEFAULT_BASE, timeout: float = 6.0, method: str = "GET"):
        self.base = (base or DEFAULT_BASE).rstrip("/")
        self.timeout = timeout
        self.method = (method or "GET").upper()
        self._config: Optional[PortalConfig] = None
        self._config_ts = 0.0
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({"User-Agent": _USER_AGENT, "Accept": "*/*"})

    # ---------- 配置发现 ----------

    def discover(self, force: bool = False) -> PortalConfig:
        if not force and self._config and time.time() - self._config_ts < self.CACHE_TTL:
            return self._config

        config = PortalConfig(base=self.base)
        try:
            resp = self.session.get(
                config.api_base() + "page/loadConfig",
                params={
                    "program_index": DEFAULT_PROGRAM_INDEX,
                    "wlan_vlan_id": "",
                    "wlan_user_ip": "",
                    "wlan_user_ssid": "",
                },
                timeout=self.timeout,
                headers={"Referer": self.base + "/"},
            )
            data = parse_jsonp(decode_best(resp.content))
            if data:
                info = data.get("data") if isinstance(data.get("data"), dict) else data
                config.program_index = str(info.get("program_index") or DEFAULT_PROGRAM_INDEX)
                config.page_index = str(info.get("page_index") or DEFAULT_PAGE_INDEX)
                config.login_method = str(info.get("login_method") or "1")
                config.account_suffix = str(info.get("account_suffix") or "")
                config.en_md5 = str(info.get("en_md5") or "0") == "1"
                config.discovered = True
        except requests.RequestException:
            pass  # 不在校园网或门户不可达时静默回退默认值

        self._config = config
        self._config_ts = time.time()
        return config

    # ---------- 工具 ----------

    @staticmethod
    def _mask(params: dict[str, str], pass_field: str) -> str:
        hide = {pass_field, "upass", "password", "Password", "user_password"}
        return "&".join(
            f"{k}={'***' if k in hide else quote(str(v), safe='')}"
            for k, v in params.items()
        )

    def _common_params(self, config: PortalConfig) -> dict[str, str]:
        return {
            "wlan_user_ip": local_ip(),
            "wlan_user_mac": local_mac(),
            "wlan_ac_ip": "",
            "wlan_ac_name": "",
            "login_method": config.login_method,
            "program_name": config.program_index,
            "page_index": config.page_index,
            "jsVersion": JS_VERSION,
        }

    # ---------- 登录 ----------

    def login(self, username: str, password: str, suffix: str = "") -> LoginResult:
        config = self.discover()
        account = f"{username or ''}{suffix or ''}"
        secret = password or ""
        if config.en_md5:
            secret = hashlib.md5(secret.encode("utf-8")).hexdigest()

        params = self._common_params(config)
        params[config.user_field] = account
        params[config.pass_field] = secret

        url = config.api_base() + "login"
        masked = f"GET {url}?{self._mask(params, config.pass_field)}"

        try:
            resp = self.session.get(
                url,
                params=params,
                timeout=self.timeout,
                headers={"Referer": self.base + "/"},
            )
        except requests.RequestException as exc:
            return LoginResult(
                ok=False,
                verdict="fail",
                message=f"无法连接认证服务器：{type(exc).__name__}",
                request=masked,
            )

        text = decode_best(resp.content)
        return self._judge(text, resp.status_code, masked)

    def _judge(self, text: str, status: int, masked_request: str) -> LoginResult:
        detail = re.sub(r"\s+", " ", text)[:600]
        data = parse_jsonp(text)

        if data is None:
            if "<title>EPortal</title>" in text:
                return LoginResult(
                    False, "unknown",
                    f"认证接口返回了门户页面而非结果（HTTP {status}），协议可能已变更",
                    status, masked_request, detail,
                )
            return LoginResult(
                False, "unknown",
                f"门户响应无法解析（HTTP {status}）",
                status, masked_request, detail,
            )

        msg = str(data.get("msg") or "").strip()
        result = str(data.get("result", data.get("code", "")))
        ret_code = str(data.get("ret_code") or "")

        if result == "1" or any(word in msg for word in _SUCCESS_WORDS):
            return LoginResult(True, "success", msg or "登录成功", status, masked_request, detail)
        if ret_code == "2" or any(word in msg for word in _ALREADY_ONLINE_WORDS):
            return LoginResult(True, "already_online", msg, status, masked_request, detail)
        return LoginResult(
            False, "fail", msg or f"认证失败（result={result}）", status, masked_request, detail
        )

    # ---------- 注销 ----------

    def logout(self) -> bool:
        config = self.discover()
        params = self._common_params(config)
        params[config.user_field] = ""
        params[config.pass_field] = ""
        try:
            resp = self.session.get(
                config.api_base() + "logout",
                params=params,
                timeout=self.timeout,
                headers={"Referer": self.base + "/"},
            )
        except requests.RequestException:
            return False
        if resp.status_code != 200:
            return False

        data = parse_jsonp(decode_best(resp.content))
        if data is None:
            return False
        msg = str(data.get("msg") or "")
        return str(data.get("result", "")) == "1" or any(w in msg for w in _LOGOUT_SUCCESS_WORDS)
