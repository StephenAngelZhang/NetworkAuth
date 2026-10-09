"""网络身份识别与连通性探测。

- 当前网络身份：Wi-Fi 用 SSID 标识（netsh），无无线连接且有默认网关则视为有线网。
- 门户可达性：直接请求门户首页（未认证时也可访问）。
- 外网连通性：请求微软/苹果的强制门户探测端点，用于判断"是否已认证上网"。
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

import requests

WIRELESS = "wireless"
ETHERNET = "ethernet"
NONE = "none"

ETHERNET_ID = "ethernet"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 强制门户探测端点：(url, 期望包含的正文片段)
_INTERNET_PROBES = (
    ("http://www.msftconnecttest.com/connecttest.txt", "Microsoft Connect Test"),
    ("http://captive.apple.com/hotspot-detect.html", "Success"),
)


@dataclass
class NetworkInfo:
    kind: str                 # wireless / ethernet / none
    id: str                   # ssid:xxx / ethernet / ""
    label: str                # 展示名

    @property
    def connected(self) -> bool:
        return self.kind != NONE

    def __str__(self) -> str:
        return self.label or "无网络"


def decode_best(raw: bytes) -> str:
    """Windows 命令输出可能是 GBK 或 UTF-8，取乱码最少的一种。"""
    best = ""
    best_bad = None
    for enc in ("gbk", "utf-8"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            text = raw.decode(enc, errors="replace")
        bad = text.count("\ufffd")
        if best_bad is None or bad < best_bad:
            best, best_bad = text, bad
        if bad == 0:
            break
    return best


def _run(cmd: list[str], timeout: float = 5.0) -> str:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if proc.returncode != 0:
        return ""
    return decode_best(proc.stdout)


def _normalize_key(key: str) -> str:
    return key.replace(".", "").replace(" ", "").strip()


def wlan_ssid() -> str:
    """返回当前已连接 Wi-Fi 的 SSID，未连接返回空串。"""
    text = _run(["netsh", "wlan", "show", "interfaces"])
    if not text:
        return ""

    for block in re.split(r"\n\s*\n", text):
        ssid = ""
        state = ""
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = _normalize_key(key).lower()
            value = value.strip()
            if key == "ssid":
                ssid = ssid or value
            elif key in ("state", "状态"):
                state = value.lower()
        if ssid and (not state or "connected" in state or "已连接" in state):
            return ssid
    return ""


def has_gateway() -> bool:
    """是否存在默认网关（用于区分有线网与无网络）。"""
    text = _run(["ipconfig"])
    if not text:
        return False
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = _normalize_key(key).lower()
        value = value.strip()
        if key in ("defaultgateway", "默认网关") and value:
            return True
    return False


def current_network() -> NetworkInfo:
    """识别当前网络身份。"""
    ssid = wlan_ssid()
    if ssid:
        return NetworkInfo(WIRELESS, f"ssid:{ssid}", ssid)
    if has_gateway():
        return NetworkInfo(ETHERNET, ETHERNET_ID, "有线网络")
    return NetworkInfo(NONE, "", "无网络")


def _session() -> requests.Session:
    session = requests.Session()
    # 忽略系统代理，避免代理导致门户探测误判
    session.trust_env = False
    session.headers.update({"User-Agent": _USER_AGENT, "Accept": "*/*"})
    return session


def portal_reachable(base: str, timeout: float = 3.0) -> bool:
    """门户首页是否可达（未认证也应可达）。"""
    try:
        resp = _session().get(base.rstrip("/") + "/", timeout=timeout)
    except requests.RequestException:
        return False
    if resp.status_code != 200:
        return False
    text = decode_best(resp.content)[:2000]
    return ("Dr.COM" in text) or ("eportal" in text) or ("doctorcom" in text.lower())


def internet_reachable(timeout: float = 3.0) -> bool:
    """是否已能正常访问外网（即已通过认证）。"""
    session = _session()
    for url, expect in _INTERNET_PROBES:
        try:
            resp = session.get(url, timeout=timeout)
        except requests.RequestException:
            continue
        if resp.status_code == 200 and expect in resp.text:
            return True
    return False


def local_ip() -> str:
    """本机在当前网络中的 IPv4 地址（尽力而为，失败返回空串）。"""
    import socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0)
        sock.connect(("10.255.255.255", 1))
        return sock.getsockname()[0]
    except OSError:
        return ""
    finally:
        try:
            sock.close()
        except OSError:
            pass
