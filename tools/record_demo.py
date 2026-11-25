"""Record frames of the real overlay on the synthetic test screen, for the README animation.

    python tools/record_demo.py shots/test150.png shots/demo_frames
Then build the GIF with tools/make_gif.py (needs Pillow, a development only dependency).

The overlay animates from `overlay.now()`. Grabbing a frame takes longer than a frame lasts, so
the overlay clock is replaced by a virtual one that advances exactly one frame per capture: the
glow entry, the shimmer and the fade in come out complete and smooth. One simple story: press
F1, drag a rectangle over a paragraph with the mouse, the translation appears in place.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drive_overlay import Driver  # noqa: E402
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from keept import i18n  # noqa: E402
from keept.platform import services  # noqa: E402

FRAME_MS = 40  # 25 fps


def draw_cursor(img: QImage, pos: QPointF) -> None:
    """A standard arrow pointer, since widget grabs do not include the mouse cursor.
    Coordinates are logical: the image carries the device pixel ratio."""
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = 1.9  # the GIF is shown at half size: a bigger pointer stays visible
    x, y = pos.x(), pos.y()
    pts = [(0, 0), (0, 17), (4.2, 13.2), (7, 19.5), (9.6, 18.4), (6.9, 12.3), (12.2, 12.3)]
    path = QPainterPath()
    path.moveTo(x, y)
    for px, py in pts[1:]:
        path.lineTo(x + px * s, y + py * s)
    path.closeSubpath()
    p.setPen(QPen(QColor(255, 255, 255), 1.6 * s))
    p.setBrush(QColor(20, 20, 20))
    p.drawPath(path)
    p.end()


def draw_key(img: QImage, label: str, pressed: bool) -> None:
    """A keycap in the top left corner, to show which key starts KeepT."""
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    w, h = 104.0, 88.0
    x, y = 28.0, 22.0 + (4 if pressed else 0)
    if not pressed:
        p.setBrush(QColor(0, 0, 0, 70))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(x, y + 7, w, h), 16, 16)
    p.setBrush(QColor(250, 250, 252))
    p.setPen(QPen(QColor(0, 212, 255) if pressed else QColor(190, 196, 206), 3.5))
    p.drawRoundedRect(QRectF(x, y, w, h), 16, 16)
    f = QFont("Segoe UI")
    f.setPixelSize(40)
    f.setWeight(QFont.DemiBold)
    p.setFont(f)
    p.setPen(QColor(30, 34, 44))
    p.drawText(QRectF(x, y, w, h), Qt.AlignCenter, label)
    p.end()


def main() -> int:
    services().init_process()
    app = QApplication(sys.argv[:1])  # noqa: F841
    i18n.set_ui_lang("en")
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    d = Driver(sys.argv[1], out, False, "es", None, False)
    # Load and warm the model first, so the recording shows the real speed of a warm KeepT.
    d.engine.translator.translate(["Hallo Welt."], "de", "es")
    vt = [0.0]
    d.ov.now = lambda: vt[0]
    dpr = d.ov.devicePixelRatioF()
    n = 0
    cursor: list[QPointF | None] = [None]

    def frame(hold_ms: int = FRAME_MS, key: str | None = None, base: QImage | None = None) -> None:
        nonlocal n
        img = base.copy() if base is not None else d.ov.grab().toImage()
        img.setDevicePixelRatio(dpr)
        if key:
            draw_key(img, "F1", key == "down")
        if cursor[0] is not None:
            draw_cursor(img, cursor[0])
        img.save(str(out / f"{n:03d}_{hold_ms}.png"))
        n += 1

    def step(hold_ms: int = FRAME_MS, key: str | None = None) -> None:
        QApplication.processEvents()
        vt[0] += hold_ms
        d.ov.repaint()
        frame(hold_ms, key)

    def film(ms: float, hold_ms: int = FRAME_MS) -> None:
        for _ in range(int(ms // hold_ms)):
            step(hold_ms)

    # 1. The plain screen, then the F1 key goes down.
    plain = QImage(sys.argv[1]).convertToFormat(QImage.Format_ARGB32)
    cursor[0] = QPointF(d.ov.width() * 0.62, d.ov.height() * 0.42)
    frame(900, "up", plain)
    frame(160, "down", plain)

    # 2. The overlay opens: frozen screen, glow entry, pill.
    d.open()
    vt[0] = 0.0
    for _ in range(5):
        step(FRAME_MS, "down")
    film(700)
    d.wait_until(lambda: d.ov.ocr_done, 5000)

    # 3. The pointer moves to the paragraph and drags a rectangle over it.
    target = d.ov.blocks[2].rect
    s = d.ov.scale
    x0, y0 = (target.x - 28) / s, (target.y - 22) / s
    x1, y1 = (target.x + target.w + 28) / s, (target.y + target.h + 22) / s
    start = cursor[0]
    for k in range(1, 11):
        e = 1 - (1 - k / 10) ** 3
        cursor[0] = QPointF(start.x() + (x0 - start.x()) * e, start.y() + (y0 - start.y()) * e)
        step()
    d._mouse(QEvent.MouseButtonPress, QPointF(x0, y0), Qt.LeftButton, Qt.LeftButton)
    for k in range(1, 19):
        t = k / 18
        e = t * t * (3 - 2 * t)
        cursor[0] = QPointF(x0 + (x1 - x0) * e, y0 + (y1 - y0) * e)
        d._mouse(QEvent.MouseMove, cursor[0], Qt.NoButton, Qt.LeftButton)
        step()
    film(200)
    d._mouse(QEvent.MouseButtonRelease, cursor[0], Qt.LeftButton, Qt.NoButton)

    # 4. Shimmer while translating, then the translation fades in over the original.
    # About half a second of shimmer (as on a warm PC), then the virtual clock stays still while
    # the real translation finishes, so saving frames does not stretch the wait in the GIF.
    film(480)
    d.wait_until(d.translation_done, 20000)
    cursor[0] = QPointF(x1 + 60, y1 + 90)  # move the pointer out of the way
    film(700)

    # 5. Hold the result so it can be read, with the glow still pulsing.
    film(1600, 100)
    frame(2600)
    d.key(Qt.Key_Escape)
    d.engine.shutdown()
    print("frames:", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
