"""应用图标：运行时用 QPainter 绘制，避免依赖二进制资源。"""

from __future__ import annotations

import struct
from typing import Iterable

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap

from app import theme

_TRAY_COLORS = {
    "online": theme.PRIMARY,
    "logging": theme.WARNING,
    "need_login": theme.WARNING,
    "no_credential": theme.WARNING,
    "failed": theme.DANGER,
    "credential_error": theme.DANGER,
    "offline": theme.OFFLINE,
    "no_network": theme.OFFLINE,
}


def render_pixmap(size: int, color: str = theme.PRIMARY, shade: str = "#60A5FA") -> QPixmap:
    """绘制蓝底圆角方 + 白色 Wi-Fi 图标。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    rect = QRectF(0, 0, size, size)
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0, QColor(shade))
    gradient.setColorAt(1, QColor(color))
    painter.setBrush(gradient)
    painter.drawRoundedRect(rect, size * 0.24, size * 0.24)

    center = QPointF(size * 0.5, size * 0.62)
    pen = QPen(QColor("#FFFFFF"))
    pen.setWidthF(max(1.0, size * 0.085))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    for ratio in (0.115, 0.205, 0.295):
        radius = size * ratio
        box = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
        # Qt 角度单位为 1/16 度，45°~135° 即上方的弧
        painter.drawArc(box, 45 * 16, 90 * 16)

    painter.setBrush(QColor("#FFFFFF"))
    painter.drawEllipse(center, size * 0.055, size * 0.055)
    painter.end()
    return pixmap


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(render_pixmap(size))
    return icon


def tray_icon(state: str = "offline") -> QIcon:
    color = _TRAY_COLORS.get(state, theme.OFFLINE)
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64):
        icon.addPixmap(render_pixmap(size, color=color, shade=_lighten(color)))
    return icon


def _lighten(color: str) -> str:
    return QColor(color).lighter(135).name()


def write_png(path: str, size: int = 256) -> None:
    render_pixmap(size).save(path, "PNG")


def write_ico(path: str, sizes: Iterable[int] = (16, 24, 32, 48, 64, 128, 256)) -> None:
    """把绘制出的图标写成 Windows ICO（PNG 容器方式）。"""
    images: list[tuple[int, bytes]] = []
    for size in sizes:
        image = render_pixmap(size).toImage()
        payload = QByteArray()
        buffer = QBuffer(payload)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()
        images.append((size, payload.data()))

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries = bytearray()
    blobs = bytearray()
    for size, png in images:
        entries += struct.pack(
            "<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset
        )
        offset += len(png)
        blobs += png

    with open(path, "wb") as handle:
        handle.write(header + bytes(entries) + bytes(blobs))
