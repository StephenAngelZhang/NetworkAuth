"""Windows DPAPI 凭据加解密。

密码只以 DPAPI 密文形式落盘，仅当前 Windows 用户可解密；
非 Windows 平台退化为可逆混淆，仅用于开发调试。
"""

from __future__ import annotations

import base64
import ctypes
import sys
from ctypes import wintypes

_IS_WIN = sys.platform == "win32"

_PREFIX = "dpapi:"
_FALLBACK_PREFIX = "plain:"


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def available() -> bool:
    """当前平台是否支持真正的加密保护。"""
    return _IS_WIN


def _make_blob(data: bytes) -> tuple[_DATA_BLOB, ctypes.Array]:
    buf = ctypes.create_string_buffer(data, len(data))
    blob = _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    return blob, buf


def _blob_bytes(blob: _DATA_BLOB) -> bytes:
    if not blob.pbData or blob.cbData == 0:
        return b""
    return ctypes.string_at(blob.pbData, blob.cbData)


def protect(plain: str) -> str:
    """加密字符串，返回可安全落盘的文本。"""
    raw = (plain or "").encode("utf-8")
    if not raw:
        return ""

    if not _IS_WIN:
        return _FALLBACK_PREFIX + base64.b64encode(raw).decode("ascii")

    crypt32 = ctypes.windll.crypt32
    in_blob, _keepalive = _make_blob(raw)
    out_blob = _DATA_BLOB()
    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "NetworkAuth",
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise OSError("CryptProtectData 调用失败")
    try:
        return _PREFIX + base64.b64encode(_blob_bytes(out_blob)).decode("ascii")
    finally:
        if out_blob.pbData:
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def unprotect(token: str) -> str:
    """还原 protect() 产出的文本。"""
    token = token or ""
    if not token:
        return ""

    if token.startswith(_FALLBACK_PREFIX):
        return base64.b64decode(token[len(_FALLBACK_PREFIX):]).decode("utf-8")

    if not token.startswith(_PREFIX):
        # 旧版本遗留的明文，直接返回兼容
        return token

    if not _IS_WIN:
        raise OSError("该密文由 Windows DPAPI 生成，无法在当前平台解密")

    crypt32 = ctypes.windll.crypt32
    raw = base64.b64decode(token[len(_PREFIX):])
    in_blob, _keepalive = _make_blob(raw)
    out_blob = _DATA_BLOB()
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise OSError("CryptUnprotectData 调用失败（可能已更换 Windows 用户）")
    try:
        return _blob_bytes(out_blob).decode("utf-8")
    finally:
        if out_blob.pbData:
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
