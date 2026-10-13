"""文件日志与全局异常捕获。

- 轮转日志写到 ``%APPDATA%\\NetworkAuth\\app.log``（1MB × 3 份，utf-8）
- 安装 ``sys.excepthook`` 与 ``threading.excepthook``，异常写入日志并通过
  ``on_error`` 回调抛出，由 ``main.py`` 转发成托盘提示
- 本模块不导入任何 GUI 库，保持 core 层零界面依赖
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import threading
import traceback
from typing import Callable, Optional

from core.config import app_dir

LOGGER_NAME = "networkauth"
LOG_FILENAME = "app.log"
MAX_BYTES = 1024 * 1024
BACKUP_COUNT = 3

logger = logging.getLogger(LOGGER_NAME)

_on_error: Optional[Callable[[str], None]] = None
_installed = False
_path = ""


def log_path() -> str:
    """当前（或默认）日志文件绝对路径。"""
    return _path or os.path.join(app_dir(), LOG_FILENAME)


def setup(level: int = logging.INFO, on_error: Optional[Callable[[str], None]] = None) -> str:
    """初始化轮转文件日志与全局异常钩子，返回日志文件绝对路径。"""
    global _on_error, _installed, _path

    _on_error = on_error
    _path = os.path.join(app_dir(), LOG_FILENAME)

    logger.setLevel(level)
    logger.propagate = False
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers):
        try:
            os.makedirs(app_dir(), exist_ok=True)
            handler: logging.Handler = logging.handlers.RotatingFileHandler(
                _path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
            )
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)-7s [%(threadName)s] %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            logger.addHandler(handler)
        except OSError as exc:  # 磁盘/权限异常时退化为仅标准错误
            logger.addHandler(logging.StreamHandler(sys.stderr))
            logger.warning("无法写入日志文件 %s：%s", _path, exc)

    if not _installed:
        sys.excepthook = _excepthook
        threading.excepthook = _threading_excepthook
        _installed = True

    logger.info("日志初始化完成：%s", _path)
    return _path


def log_exception(exc_type, exc_value, exc_tb, *, context: str = "") -> str:
    """记录异常堆栈并触发 on_error 回调，返回给用户看的单行摘要。"""
    if issubclass(exc_type, KeyboardInterrupt):
        return ""

    prefix = f"{context} " if context else ""
    detail = "".join(traceback.format_exception(exc_type, exc_value, exc_tb)).rstrip()
    logger.error("%s未捕获异常：\n%s", prefix, detail)

    summary = f"{prefix}{exc_type.__name__}: {exc_value}".strip()
    if _on_error is not None:
        try:
            _on_error(summary)
        except Exception:  # 回调本身出错不能再抛，否则递归
            logger.exception("异常回调执行失败")
    return summary


def _excepthook(exc_type, exc_value, exc_tb) -> None:
    log_exception(exc_type, exc_value, exc_tb, context="主线程")


def _threading_excepthook(args) -> None:
    thread = getattr(args, "thread", None)
    name = getattr(thread, "name", "") or ""
    log_exception(
        args.exc_type,
        args.exc_value,
        args.exc_traceback,
        context=f"线程[{name}]" if name else "子线程",
    )
