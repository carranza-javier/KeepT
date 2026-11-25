"""App icon drawn in code (gradient lens with a "T"), so it is crisp at every size."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QConicalGradient, QFont, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap

from .overlay.effects import brand_gradient

SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def render_icon(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    r = QRectF(0, 0, size, size).adjusted(size * 0.04, size * 0.04, -size * 0.04, -size * 0.04)
    g = brand_gradient(r)  # KettenKI 135 degree cyan -> green
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


_cache: dict[int, QImage] = {}


def paint_app_icon(p: QPainter, r: QRectF, color: QColor | None = None) -> None:
    """Draw the app icon inside `r` (pill buttons, welcome pill), rendered at the device's real
    pixel size so it stays sharp at 125 % or 150 %. `color` is ignored: the icon keeps its colours."""
    dpr = p.device().devicePixelRatioF() if p.device() is not None else 1.0
    px = max(8, round(min(r.width(), r.height()) * dpr))
    img = _cache.get(px)
    if img is None:
        img = _cache[px] = render_icon(px)
    side = px / dpr
    p.drawImage(QRectF(r.center().x() - side / 2, r.center().y() - side / 2, side, side), img)


def app_icon() -> QIcon:
    icon = QIcon()
    for s in SIZES:
        icon.addPixmap(QPixmap.fromImage(render_icon(s)))
    return icon
