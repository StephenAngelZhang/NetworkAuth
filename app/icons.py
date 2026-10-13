"""应用图标与状态徽标：运行时用 QPainter 绘制，不依赖二进制资源。

对外提供：

- ``app_icon()`` / ``render_pixmap()``：品牌图标（蓝底白 Wi-Fi）
- ``tray_icon(state)``：按状态着色的托盘图标
- ``badge_pixmap(glyph, size, color, tint)``：状态卡左侧的图标化徽标
- ``write_png()`` / ``write_ico()``：把品牌图标落盘成 resources/app.ico 的构建工具
"""

from __future__ import annotations

import struct
from typing import Iterable

from PyQt6.QtCore import (
    QBuffer,
    QByteArray,
    QIODevice,
    QLineF,
    QPointF,
    QRectF,
    Qt,
)
from PyQt6.QtGui import (
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from app import theme

# --------------------------------------------------------------------------- 品牌图标


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
    color = theme.STATE_COLORS.get(state, theme.OFFLINE)
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64):
        icon.addPixmap(render_pixmap(size, color=color, shade=_lighten(color)))
    return icon


def _lighten(color: str) -> str:
    return QColor(color).lighter(135).name()


# --------------------------------------------------------------------------- 状态徽标


def glyph_pixmap(glyph: str, size: int, color: str) -> QPixmap:
    """绘制单色线性图标（check / clock / alert / off）。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(max(1.3, size * 0.105))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if glyph == "check":
        path = QPainterPath()
        path.moveTo(size * 0.26, size * 0.54)
        path.lineTo(size * 0.43, size * 0.71)
        path.lineTo(size * 0.75, size * 0.33)
        painter.drawPath(path)
    elif glyph == "clock":
        painter.drawEllipse(QPointF(size * 0.5, size * 0.5), size * 0.32, size * 0.32)
        painter.drawLine(QLineF(size * 0.5, size * 0.5, size * 0.5, size * 0.30))
        painter.drawLine(QLineF(size * 0.5, size * 0.5, size * 0.66, size * 0.57))
    elif glyph == "off":
        painter.drawArc(
            QRectF(size * 0.18, size * 0.20, size * 0.64, size * 0.64),
            120 * 16,
            300 * 16,
        )
        painter.drawLine(QLineF(size * 0.5, size * 0.14, size * 0.5, size * 0.50))
    else:  # alert
        painter.drawLine(QLineF(size * 0.5, size * 0.24, size * 0.5, size * 0.56))
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(size * 0.5, size * 0.74), size * 0.062, size * 0.062)

    painter.end()
    return pixmap


def badge_pixmap(glyph: str, size: int, color: str, tint: str) -> QPixmap:
    """绘制"浅色圆底 + 线性图标"的状态徽标。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(tint))
    painter.drawEllipse(QRectF(0, 0, size, size))

    inner_size = max(10, int(size * 0.56))
    inner = glyph_pixmap(glyph, inner_size, color)
    offset = (size - inner_size) / 2.0
    painter.drawPixmap(QPointF(offset, offset), inner)
    painter.end()
    return pixmap


# --------------------------------------------------------------------------- 构建工具


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
