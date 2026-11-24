"""App icon drawn in code (gradient lens with a "T"), so it is crisp at every size."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QConicalGradient, QFont, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap

from .overlay.effects import PALETTE

SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def render_icon(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    r = QRectF(0, 0, size, size).adjusted(size * 0.04, size * 0.04, -size * 0.04, -size * 0.04)
    g = QConicalGradient(r.center(), 120)
    n = len(PALETTE)
    for i in range(n + 1):
        g.setColorAt(i / n, PALETTE[i % n])
    ring = max(1.6, size * 0.11)
    p.setPen(QPen(g, ring))
    p.setBrush(QColor(22, 24, 32))
    inner = r.adjusted(ring / 2, ring / 2, -ring / 2, -ring / 2)
    p.drawEllipse(inner)
    f = QFont("Segoe UI")
    f.setPixelSize(max(8, int(size * 0.56)))
    f.setWeight(QFont.Bold)
    p.setFont(f)
    p.setPen(QColor(255, 255, 255))
    p.drawText(inner.adjusted(0, -size * 0.02, 0, 0), Qt.AlignCenter, "T")
    p.end()
    return img


def app_icon() -> QIcon:
    icon = QIcon()
    for s in SIZES:
        icon.addPixmap(QPixmap.fromImage(render_icon(s)))
    return icon
