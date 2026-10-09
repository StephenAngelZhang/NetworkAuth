"""开机自启（写 HKCU\\...\\Run，无需管理员权限）。"""

from __future__ import annotations

import os
import sys
from typing import Optional

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "NetworkAuth"

_IS_WIN = sys.platform == "win32"


def _open_run_key(write: bool = False):
    import winreg

    return winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        RUN_KEY,
        0,
        winreg.KEY_WRITE | winreg.KEY_READ if write else winreg.KEY_READ,
    )


def launch_command() -> str:
    """开机自启时执行的命令行。"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'

    python_exe = sys.executable
    pythonw = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
    if os.path.exists(pythonw):
        python_exe = pythonw

    script = os.path.abspath(sys.argv[0] if sys.argv and sys.argv[0] else "main.py")
    return f'"{python_exe}" "{script}" --minimized'


def is_enabled() -> bool:
    if not _IS_WIN:
        return False
    try:
        import winreg

        with _open_run_key() as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
    except OSError:
        return False
    return bool(value)


def set_enabled(enabled: bool) -> bool:
    """开启/关闭开机自启，返回操作是否成功。"""
    if not _IS_WIN:
        return False
    try:
        import winreg

        with _open_run_key(write=True) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, launch_command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except OSError:
                    pass
    except OSError:
        return False
    return True


def current_command() -> Optional[str]:
    if not _IS_WIN:
        return None
    try:
        import winreg

        with _open_run_key() as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
    except OSError:
        return None
    return value
