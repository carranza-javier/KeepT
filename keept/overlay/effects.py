"""Animated effects drawn with QPainter: edge glow, selection stroke, shimmer and icons.

Colours: the KettenKI brand gradient, 135 degrees from #00d4ff (cyan) to #00ff88 (green),
plus in-between tones and lighter variants so the wave running along the edges has life.
On light parts of the screen the green barely contrasts, so a darker, more saturated set of
the same hues is used there (chosen per zone from the frozen screenshot).
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QConicalGradient, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QRegion

BRAND_CYAN = QColor("#00d4ff")
BRAND_GREEN = QColor("#00ff88")
BRAND_ANGLE = 135.0  # degrees, CSS convention (towards the bottom right)

# Cyclic stops for the conical sweep: cyan, a lighter cyan crest, the cyan-green middle,
# green, a lighter green crest and back. Light crests read as a travelling wave.
PALETTE_ON_DARK = [QColor("#00d4ff"), QColor("#8ff0ff"), QColor("#00eac4"), QColor("#00ff88"),
                   QColor("#8fffc8"), QColor("#00eac4")]
# Same hues, darker and more saturated, for light backgrounds (contrast against white).
PALETTE_ON_LIGHT = [QColor("#0099d1"), QColor("#00b8ec"), QColor("#00a8a0"), QColor("#00a85c"),
                    QColor("#00c46c"), QColor("#00a8a0")]
PALETTE = PALETTE_ON_DARK


def brand_gradient(rect: QRectF, light_bg: bool = False) -> QLinearGradient:
    """The 135 degree brand gradient across `rect` (top left cyan to bottom right green)."""
    g = QLinearGradient(rect.topLeft(), rect.bottomRight())
    if light_bg:
        g.setColorAt(0, QColor("#0099d1"))
        g.setColorAt(1, QColor("#00a85c"))
    else:
        g.setColorAt(0, BRAND_CYAN)
        g.setColorAt(1, BRAND_GREEN)
    return g

ENTRY_MS = 500.0
PULSE_PERIOD_S = 2.6


def ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def conical(center: QPointF, angle: float, alpha: float = 1.0, palette=None) -> QConicalGradient:
    palette = palette or PALETTE_ON_DARK
    g = QConicalGradient(center, angle)
    n = len(palette)
    for i in range(n + 1):
        c = QColor(palette[i % n])
        c.setAlphaF(max(0.0, min(1.0, alpha)))
        g.setColorAt(i / n, c)
    return g


class EdgeGlow:
    """Coloured glow running along the screen edges: ~500 ms entry, then a subtle pulse."""

    DOWNSCALE = 4

    def __init__(self) -> None:
        self.level = 1.0  # extra multiplier (lowered while a translation is shown)
        self._buf: QImage | None = None
        self._buf_light: QImage | None = None
        self._mask: QImage | None = None  # alpha = how light the screen is there (low res)
        self._light_region: QRegion | None = None  # light zones, logical px

    def set_background(self, lightness, logical_size) -> None:
        """`lightness`: 2D float array (0 dark .. 1 light) of the capture, any resolution.
        Builds the low resolution mask used to pick the palette per zone."""
        import numpy as np

        if lightness is None:
            self._mask = None
            self._light_region = None
            return
        f = self.DOWNSCALE
        w = max(8, math.ceil(logical_size.width() / f))
        h = max(8, math.ceil(logical_size.height() / f))
        ys = np.linspace(0, lightness.shape[0] - 1, h).astype(int)
        xs = np.linspace(0, lightness.shape[1] - 1, w).astype(int)
        small = lightness[np.ix_(ys, xs)]
        # Light zones: relative luminance above ~0.5, with a soft transition.
        alpha = np.clip((small - 0.42) / 0.2, 0.0, 1.0)
        a8 = np.ascontiguousarray((alpha * 255).astype(np.uint8))
        argb = np.zeros((h, w, 4), np.uint8)
        argb[..., 3] = a8
        argb[..., 0] = a8
        argb[..., 1] = a8
        argb[..., 2] = a8  # premultiplied white
        self._mask = QImage(argb.data, w, h, w * 4, QImage.Format_ARGB32_Premultiplied).copy()
        bits = QImage(np.ascontiguousarray(np.where(alpha >= 0.5, 255, 0).astype(np.uint8)).data, w, h, w,
                      QImage.Format_Grayscale8).copy()
        from PySide6.QtGui import QBitmap, QTransform

        region = QRegion(QBitmap.fromImage(bits.createMaskFromColor(0xFF000000, Qt.MaskOutColor)))
        self._light_region = QTransform.fromScale(f, f).map(region)

    def is_light_at(self, x: float, y: float) -> bool:
        """Whether the screen is light at a logical point (for the selection stroke)."""
        if self._mask is None:
            return False
        f = self.DOWNSCALE
        px = int(min(max(x / f, 0), self._mask.width() - 1))
        py = int(min(max(y / f, 0), self._mask.height() - 1))
        return self._mask.pixelColor(px, py).alpha() >= 128

    def _render_rings(self, buf: QImage, palette, angle, k, core, tail, reach) -> None:
        f = self.DOWNSCALE
        buf.fill(Qt.transparent)
        small = QRectF(0, 0, buf.width(), buf.height())
        q = QPainter(buf)
        q.setRenderHint(QPainter.Antialiasing)
        q.setBrush(Qt.NoBrush)
        grad = conical(small.center(), angle, palette=palette)
        # Thin, non overlapping rings whose opacity falls off smoothly from the edge inwards
        # (bright core plus exponential tail): no visible bands, even on dark backgrounds.
        step = 0.5
        d = 0.0
        while d < reach / f:
            dist = d * f
            alpha = 0.95 if dist < core else 0.7 * math.exp(-(dist - core) / tail)
            pen = QPen(QBrush(grad), step)
            pen.setJoinStyle(Qt.MiterJoin)
            q.setPen(pen)
            q.setOpacity(min(1.0, alpha * k))
            inset = d + step / 2
            q.drawRect(small.adjusted(inset, inset, -inset, -inset))
            d += step
        q.end()

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
        grow = 0.55 + 0.45 * ease_out_cubic(min(1.0, elapsed_ms / ENTRY_MS))
        angle = self.angle(elapsed_ms)
        f = self.DOWNSCALE
        core = glow_px * 0.3 * grow
        tail = glow_px * 0.75 * grow
        reach = core + tail * 4.0

        # The glow is soft, so it is rendered at 1/4 resolution and scaled up smoothly
        # (16 ms -> ~2 ms per frame at 1920x1200).
        w, h = max(8, math.ceil(rect.width() / f)), max(8, math.ceil(rect.height() / f))
        if self._buf is None or self._buf.width() != w or self._buf.height() != h:
            self._buf = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
            self._buf_light = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        mask = self._mask if self._mask is not None and self._mask.size() == self._buf.size() else None
        self._render_rings(self._buf, PALETTE_ON_DARK, angle, k, core, tail, reach)
        if mask is not None:
            # Keep the bright palette only on dark zones and the deep palette only on light ones.
            self._render_rings(self._buf_light, PALETTE_ON_LIGHT, angle, k, core, tail, reach)
            q = QPainter(self._buf)
            q.setCompositionMode(QPainter.CompositionMode_DestinationOut)
            q.drawImage(0, 0, mask)
            q.end()
            q = QPainter(self._buf_light)
            q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            q.drawImage(0, 0, mask)
            q.end()

        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        border = QRegion(rect.toAlignedRect()).subtracted(
            QRegion(rect.adjusted(reach + f, reach + f, -reach - f, -reach - f).toAlignedRect()))
        p.setClipRegion(border)
        p.drawImage(rect, self._buf)
        if mask is not None:
            p.drawImage(rect, self._buf_light)
        # Crisp line right at the edge, at full resolution, in the palette of each zone.
        width = max(1.5, core)
        inset = width / 2
        edge = rect.adjusted(inset, inset, -inset, -inset)
        p.setBrush(Qt.NoBrush)
        p.setOpacity(min(1.0, 0.9 * k))
        zones = [(PALETTE_ON_DARK, None)]
        if mask is not None and self._light_region is not None:
            zones = [(PALETTE_ON_DARK, border.subtracted(self._light_region)),
                     (PALETTE_ON_LIGHT, border.intersected(self._light_region))]
        for palette, clip in zones:
            if clip is not None:
                p.setClipRegion(clip)
            else:
                p.setClipping(False)
            pen = QPen(QBrush(conical(rect.center(), angle, palette=palette)), width)
            pen.setJoinStyle(Qt.MiterJoin)
            p.setPen(pen)
            p.drawRect(edge)
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


def paint_stroke(p: QPainter, path: QPainterPath, center: QPointF, angle: float, width: float, alpha: float = 1.0,
                 light_bg: bool = False) -> None:
    """White stroke with a coloured glow (colours follow the edge gradient; deeper tones
    when the stroke is drawn over a light part of the screen)."""
    if alpha <= 0.01:
        return
    p.save()
    p.setBrush(Qt.NoBrush)
    grad = conical(center, angle, palette=PALETTE_ON_LIGHT if light_bg else PALETTE_ON_DARK)
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
