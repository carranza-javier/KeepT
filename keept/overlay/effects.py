"""Animated effects drawn with QPainter: edge glow, selection stroke, shimmer and icons.

Palette "Aurora": teal, azure, violet, magenta and amber. Vivid like Circle to
Search but with its own hues; checked on light and dark captures.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QConicalGradient, QLinearGradient, QPainter, QPainterPath, QPen

PALETTE = [QColor("#00D9C0"), QColor("#3A7BFF"), QColor("#8E5BFF"), QColor("#FF4F9A"), QColor("#FFB23F")]

ENTRY_MS = 500.0
PULSE_PERIOD_S = 2.6


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def conical(center: QPointF, angle: float, alpha: float = 1.0) -> QConicalGradient:
    g = QConicalGradient(center, angle)
    n = len(PALETTE)
    for i in range(n + 1):
        c = QColor(PALETTE[i % n])
        c.setAlphaF(max(0.0, min(1.0, alpha)))
        g.setColorAt(i / n, c)
    return g


class EdgeGlow:
    """Coloured glow running along the screen edges: ~500 ms entry, then a subtle pulse."""

    def __init__(self) -> None:
        self.level = 1.0  # extra multiplier (lowered while a translation is shown)

    def intensity(self, elapsed_ms: float) -> float:
        if elapsed_ms < ENTRY_MS:
            t = elapsed_ms / ENTRY_MS
            # Rise with a small overshoot that settles into the pulse.
            return ease_out_cubic(t) * (1.0 + 0.25 * math.sin(math.pi * t))
        t = (elapsed_ms - ENTRY_MS) / 1000.0
        return 0.82 + 0.18 * math.cos(2 * math.pi * t / PULSE_PERIOD_S)

    def angle(self, elapsed_ms: float) -> float:
        # Fast sweep during the entry, then a slow rotation.
        entry = ease_out_cubic(min(1.0, elapsed_ms / ENTRY_MS)) * 140.0
        return (90.0 + entry + elapsed_ms * 0.02) % 360.0

    def paint(self, p: QPainter, rect: QRectF, elapsed_ms: float, glow_px: float) -> None:
        k = self.intensity(elapsed_ms) * self.level
        if k <= 0.01:
            return
        grow = ease_out_cubic(min(1.0, elapsed_ms / ENTRY_MS))
        grad = conical(rect.center(), self.angle(elapsed_ms))
        p.save()
        p.setBrush(Qt.NoBrush)
        # Fake gaussian blur: wide faint strokes plus a crisp line. Strokes are centred
        # on the edge so only the inner half is visible.
        passes = ((4.2, 0.10), (2.8, 0.16), (1.8, 0.26), (1.0, 0.45), (0.45, 0.85))
        for width, alpha in passes:
            pen = QPen(QBrush(grad), 2 * glow_px * width * (0.55 + 0.45 * grow))
            pen.setJoinStyle(Qt.MiterJoin)
            p.setPen(pen)
            p.setOpacity(min(1.0, alpha * k))
            p.drawRect(rect)
        p.restore()

    @staticmethod
    def dirty_margin(glow_px: float) -> float:
        return glow_px * 4.4 + 2


def smooth_path(points: list[QPointF]) -> QPainterPath:
    path = QPainterPath()
    if not points:
        return path
    path.moveTo(points[0])
    if len(points) < 3:
        for pt in points[1:]:
            path.lineTo(pt)
        return path
    for i in range(1, len(points) - 1):
        mid = (points[i] + points[i + 1]) / 2
        path.quadTo(points[i], mid)
    path.lineTo(points[-1])
    return path


def paint_stroke(p: QPainter, path: QPainterPath, center: QPointF, angle: float, width: float, alpha: float = 1.0) -> None:
    """White stroke with a coloured glow (colours follow the edge gradient)."""
    if alpha <= 0.01:
        return
    p.save()
    p.setBrush(Qt.NoBrush)
    grad = conical(center, angle)
    for w, a in ((width * 5.0, 0.12), (width * 3.0, 0.25), (width * 1.8, 0.55)):
        pen = QPen(QBrush(grad), w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        p.setOpacity(a * alpha)
        p.drawPath(path)
    p.setOpacity(alpha)
    p.setPen(QPen(QColor(255, 255, 255), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(path)
    p.restore()


def paint_shimmer(p: QPainter, rect: QRectF, radius: float, bg: QColor, elapsed_ms: float, alpha: float = 1.0) -> None:
    """Placeholder for a block whose translation is still on its way."""
    p.save()
    p.setOpacity(alpha)
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    base = QColor(bg)
    base.setAlpha(225)
    p.fillPath(path, base)
    dark = bg.lightnessF() < 0.5
    hi = QColor(255, 255, 255, 70 if dark else 150)
    band = max(rect.width() * 0.45, 60.0)
    period = 1100.0
    pos = (elapsed_ms % period) / period
    x = rect.left() - band + (rect.width() + 2 * band) * ease_in_out(pos)
    g = QLinearGradient(QPointF(x - band / 2, rect.top()), QPointF(x + band / 2, rect.bottom()))
    clear = QColor(hi)
    clear.setAlpha(0)
    g.setColorAt(0.0, clear)
    g.setColorAt(0.5, hi)
    g.setColorAt(1.0, clear)
    p.setClipPath(path)
    p.fillRect(rect, QBrush(g))
    p.restore()


# -- icons (drawn, so they follow the theme colour and DPI) ---------------------
def icon_sparkle(p: QPainter, r: QRectF, color: QColor) -> None:
    c = r.center()
    s = min(r.width(), r.height()) / 2
    path = QPainterPath()
    path.moveTo(c.x(), c.y() - s)
    path.quadTo(c.x() + s * 0.12, c.y() - s * 0.12, c.x() + s, c.y())
    path.quadTo(c.x() + s * 0.12, c.y() + s * 0.12, c.x(), c.y() + s)
    path.quadTo(c.x() - s * 0.12, c.y() + s * 0.12, c.x() - s, c.y())
    path.quadTo(c.x() - s * 0.12, c.y() - s * 0.12, c.x(), c.y() - s)
    g = QLinearGradient(r.topLeft(), r.bottomRight())
    g.setColorAt(0, PALETTE[0])
    g.setColorAt(0.5, PALETTE[1])
    g.setColorAt(1, PALETTE[3])
    p.fillPath(path, QBrush(g))


def icon_copy(p: QPainter, r: QRectF, color: QColor) -> None:
    s = min(r.width(), r.height())
    pen = QPen(color, max(1.2, s * 0.09))
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    back = QRectF(r.left() + s * 0.30, r.top() + s * 0.08, s * 0.58, s * 0.66)
    front = QRectF(r.left() + s * 0.12, r.top() + s * 0.26, s * 0.58, s * 0.66)
    p.drawRoundedRect(back, s * 0.12, s * 0.12)
    bg_path = QPainterPath()
    bg_path.addRoundedRect(front, s * 0.12, s * 0.12)
    p.drawPath(bg_path)


def icon_eye(p: QPainter, r: QRectF, color: QColor) -> None:
    s = min(r.width(), r.height())
    c = r.center()
    pen = QPen(color, max(1.2, s * 0.09))
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(c.x() - s * 0.48, c.y())
    path.quadTo(c.x(), c.y() - s * 0.62, c.x() + s * 0.48, c.y())
    path.quadTo(c.x(), c.y() + s * 0.62, c.x() - s * 0.48, c.y())
    p.drawPath(path)
    p.setBrush(color)
    p.drawEllipse(c, s * 0.13, s * 0.13)


def icon_chevron(p: QPainter, r: QRectF, color: QColor) -> None:
    s = min(r.width(), r.height())
    c = r.center()
    pen = QPen(color, max(1.2, s * 0.12), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    path = QPainterPath()
    path.moveTo(c.x() - s * 0.28, c.y() - s * 0.12)
    path.lineTo(c.x(), c.y() + s * 0.16)
    path.lineTo(c.x() + s * 0.28, c.y() - s * 0.12)
    p.drawPath(path)


def icon_check(p: QPainter, r: QRectF, color: QColor) -> None:
    s = min(r.width(), r.height())
    c = r.center()
    pen = QPen(color, max(1.4, s * 0.12), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    path = QPainterPath()
    path.moveTo(c.x() - s * 0.32, c.y())
    path.lineTo(c.x() - s * 0.08, c.y() + s * 0.24)
    path.lineTo(c.x() + s * 0.34, c.y() - s * 0.24)
    p.drawPath(path)


def icon_arrow(p: QPainter, r: QRectF, color: QColor) -> None:
    s = min(r.width(), r.height())
    c = r.center()
    pen = QPen(color, max(1.2, s * 0.1), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    path = QPainterPath()
    path.moveTo(c.x() - s * 0.36, c.y())
    path.lineTo(c.x() + s * 0.36, c.y())
    path.moveTo(c.x() + s * 0.12, c.y() - s * 0.24)
    path.lineTo(c.x() + s * 0.36, c.y())
    path.lineTo(c.x() + s * 0.12, c.y() + s * 0.24)
    p.drawPath(path)
