"""Render a fake desktop with known text (de/en/es, light and dark panels) to a PNG.

Used to verify OCR, block grouping and the overlay while the real screen is not
available (for example when the Windows session is locked).

    python tools/make_test_screen.py out.png --width 1920 --height 1200 --scale 1.5
"""

from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPainterPath

PANELS = [
    # (x, y, w, h, bg, fg, title, body)
    (0.03, 0.05, 0.44, 0.40, "#ffffff", "#202124", "Datenschutzeinstellungen",
     "Wir verwenden Cookies, um Inhalte zu personalisieren und die Zugriffe auf unsere Website zu analysieren. "
     "Sie können Ihre Auswahl jederzeit in den Einstellungen ändern."),
    (0.53, 0.05, 0.44, 0.40, "#1f2430", "#e8eaed", "Release notes",
     "This update improves battery life and fixes a crash that happened when opening large files. "
     "Restart the application to finish installing the update."),
    (0.03, 0.52, 0.44, 0.40, "#fdf6e3", "#3b3b3b", "Configuración de la cuenta",
     "No se pudo guardar el archivo. Comprueba que tienes espacio suficiente en el disco e inténtalo de nuevo más tarde."),
    (0.53, 0.52, 0.44, 0.40, "#0b57d0", "#ffffff", "Willkommen zurück",
     "Melden Sie sich an, um auf Ihre Dateien zuzugreifen."),
]

BUTTONS = [
    (0.06, 0.37, "Alle akzeptieren", "#0b57d0", "#ffffff"),
    (0.20, 0.37, "Ablehnen", "#e8eaed", "#202124"),
    (0.56, 0.37, "Restart now", "#8ab4f8", "#1f2430"),
    (0.06, 0.84, "Guardar cambios", "#3b3b3b", "#fdf6e3"),
]


def render(width: int, height: int, scale: float, page_bg: str = "#c9d3e0") -> QImage:
    img = QImage(width, height, QImage.Format_RGB32)
    img.fill(QColor(page_bg))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    px = lambda v: int(round(v * scale))  # noqa: E731
    for x, y, w, h, bg, fg, title, body in PANELS:
        r = QRectF(x * width, y * height, w * width, h * height)
        path = QPainterPath()
        path.addRoundedRect(r, px(10), px(10))
        p.fillPath(path, QColor(bg))
        p.setPen(QColor(fg))
        f = QFont("Segoe UI")
        f.setPixelSize(px(22))
        f.setBold(True)
        p.setFont(f)
        p.drawText(r.adjusted(px(24), px(20), -px(24), 0), Qt.AlignLeft | Qt.AlignTop, title)
        f.setBold(False)
        f.setPixelSize(px(14))
        p.setFont(f)
        p.drawText(r.adjusted(px(24), px(62), -px(24), -px(60)), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, body)
    for x, y, label, bg, fg in BUTTONS:
        f = QFont("Segoe UI")
        f.setPixelSize(px(14))
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        tw = p.fontMetrics().horizontalAdvance(label)
        r = QRectF(x * width, y * height, tw + px(32), px(34))
        path = QPainterPath()
        path.addRoundedRect(r, px(17), px(17))
        p.fillPath(path, QColor(bg))
        p.setPen(QColor(fg))
        p.drawText(r, Qt.AlignCenter, label)
    p.end()
    return img


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1200)
    ap.add_argument("--scale", type=float, default=1.5)
    ap.add_argument("--page-bg", default="#c9d3e0")
    args = ap.parse_args()
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)  # noqa: F841
    render(args.width, args.height, args.scale, args.page_bg).save(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
