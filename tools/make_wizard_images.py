"""Write the installer images (KeepT icon instead of Inno Setup's defaults) to packaging/wizard/.

    python tools/make_wizard_images.py
Small image: top right of every page (white header). Large image: welcome and finish pages.
One file per display scaling, as Inno Setup picks the closest size.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter  # noqa: E402

from keept.icon import render_icon  # noqa: E402

SCALES = {"100": 1.0, "125": 1.25, "150": 1.5, "200": 2.0}
SMALL = 55  # px at 100 %
LARGE = (164, 314)


def small(scale: float) -> QImage:
    n = round(SMALL * scale)
    img = QImage(n, n, QImage.Format_RGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    pad = round(n * 0.06)
    p.drawImage(QRectF(pad, pad, n - 2 * pad, n - 2 * pad), render_icon(n - 2 * pad))
    p.end()
    return img


def large(scale: float) -> QImage:
    w, h = round(LARGE[0] * scale), round(LARGE[1] * scale)
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0.0, QColor(28, 31, 40))
    g.setColorAt(1.0, QColor(16, 18, 24))
    p.fillRect(img.rect(), g)
    side = round(w * 0.62)
    p.drawImage(QRectF((w - side) / 2, h * 0.30, side, side), render_icon(side))
    p.end()
    return img


def main() -> int:
    app = QGuiApplication(sys.argv[:1])  # noqa: F841
    out = ROOT / "packaging" / "wizard"
    out.mkdir(parents=True, exist_ok=True)
    for name, scale in SCALES.items():
        small(scale).save(str(out / f"small-{name}.bmp"), "BMP")
        large(scale).save(str(out / f"large-{name}.bmp"), "BMP")
    print("wrote", sorted(p.name for p in out.iterdir()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
