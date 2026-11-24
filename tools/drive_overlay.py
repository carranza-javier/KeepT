"""Drive the real overlay with synthetic input and save frames, to review it visually.

Works without touching the real mouse/keyboard (events are posted to the widget),
so it also runs while the Windows session is locked.

    python tools/drive_overlay.py shots/test150.png --out shots/run --scenario all
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QKeyEvent, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from keept import i18n  # noqa: E402
from keept.app import load_image_bgra  # noqa: E402
from keept.capture import Capture  # noqa: E402
from keept.engine import Engine  # noqa: E402
from keept.overlay.overlay_window import OverlayWindow, State  # noqa: E402
from keept.platform import MonitorInfo, services  # noqa: E402


class Driver:
    def __init__(self, image: str, out: Path, dark: bool, target: str, device: str | None, debug_blocks: bool):
        self.out = out
        out.mkdir(parents=True, exist_ok=True)
        self.engine = Engine()
        self.ov = OverlayWindow(self.engine, target, dark, debug_blocks=debug_blocks)
        bgra = load_image_bgra(image)
        h, w = bgra.shape[:2]
        screens = {s.name(): s for s in QGuiApplication.screens()}
        if device is None:
            device = next(n for n, s in screens.items() if round(s.geometry().width() * s.devicePixelRatio()) == w)
        s = screens[device]
        g = s.geometry()
        self.capture = Capture(MonitorInfo(device, g.x(), g.y(), w, h, s.devicePixelRatio()), bgra)
        self.frame = 0

    def pump(self, ms: float) -> None:
        end = time.perf_counter() + ms / 1000
        while time.perf_counter() < end:
            QApplication.processEvents()
            time.sleep(0.004)

    def wait_until(self, cond, timeout_ms: float = 120000) -> bool:
        end = time.perf_counter() + timeout_ms / 1000
        while time.perf_counter() < end:
            QApplication.processEvents()
            if cond():
                return True
            time.sleep(0.01)
        return False

    def shot(self, name: str) -> Path:
        self.frame += 1
        path = self.out / f"{self.frame:02d}_{name}.png"
        self.ov.grab().save(str(path))
        print("saved", path)
        return path

    def open(self) -> None:
        self.ov.open(self.capture, time.perf_counter())

    def phys_to_logical(self, x: float, y: float) -> QPointF:
        return QPointF(x / self.ov.scale, y / self.ov.scale)

    def _mouse(self, kind, pos: QPointF, button, buttons) -> None:
        ev = QMouseEvent(kind, pos, self.ov.mapToGlobal(pos), button, buttons, Qt.NoModifier)
        QApplication.sendEvent(self.ov, ev)

    def drag(self, points_phys, shot_mid: str | None = None) -> None:
        pts = [self.phys_to_logical(x, y) for x, y in points_phys]
        self._mouse(QEvent.MouseButtonPress, pts[0], Qt.LeftButton, Qt.LeftButton)
        for i, p in enumerate(pts[1:], 1):
            self._mouse(QEvent.MouseMove, p, Qt.NoButton, Qt.LeftButton)
            self.pump(4)
            if shot_mid and i == int(len(pts) * 0.85):
                self.pump(20)
                self.shot(shot_mid)
        self._mouse(QEvent.MouseButtonRelease, pts[-1], Qt.LeftButton, Qt.NoButton)

    def click(self, x: float, y: float) -> None:
        self.drag([(x, y), (x + 1, y)])

    def key(self, key, release: bool = True) -> None:
        QApplication.sendEvent(self.ov, QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier))
        if release:
            QApplication.sendEvent(self.ov, QKeyEvent(QEvent.KeyRelease, key, Qt.NoModifier))

    def translation_done(self) -> bool:
        return self.ov.state == State.SHOWING and not any(i.status == "pending" for i in self.ov.items.values())


def lasso_around(rect, margin=30, n=60):
    cx, cy = rect.cx, rect.cy
    rx, ry = rect.w / 2 + margin, rect.h / 2 + margin
    return [(cx + rx * math.cos(2 * math.pi * i / n - 2.0), cy + ry * math.sin(2 * math.pi * i / n - 2.0)) for i in range(n + 3)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--out", default="shots/run")
    ap.add_argument("--scenario", default="all")
    ap.add_argument("--dark", action="store_true")
    ap.add_argument("--target", default="es")
    ap.add_argument("--device")
    ap.add_argument("--debug-blocks", action="store_true")
    args = ap.parse_args()

    services().init_process()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1])  # noqa: F841
    i18n.set_ui_lang(services().system_language())
    d = Driver(args.image, Path(args.out), args.dark, args.target, args.device, args.debug_blocks)
    sc = args.scenario

    d.open()
    d.pump(110)
    d.shot("entry_110ms")
    d.pump(600)
    d.shot("ready")
    d.wait_until(lambda: d.ov.ocr_done, 5000)
    print("blocks:", [(b.id, b.lang, b.text[:30]) for b in d.ov.blocks])

    if sc in ("all", "lasso"):
        target = d.ov.blocks[min(2, len(d.ov.blocks) - 1)]
        d.drag(lasso_around(target.rect), shot_mid="lasso_drawing")
        d.pump(60)
        d.shot("lasso_pending")
        ok = d.wait_until(d.translation_done)
        d.pump(400)
        d.shot("lasso_translated" if ok else "lasso_timeout")

    if sc in ("all", "rect"):
        b = d.ov.blocks[-1]
        r = b.rect
        pts = [(r.x - 20 + i * (r.w + 40) / 20, r.y - 15 + i * (r.h + 30) / 20) for i in range(21)]
        d.drag(pts, shot_mid="rect_drawing")
        d.wait_until(d.translation_done)
        d.pump(400)
        d.shot("rect_translated")

    if sc in ("all", "click"):
        b = d.ov.blocks[0]
        d.click(b.rect.cx, b.rect.cy)
        d.wait_until(d.translation_done)
        d.pump(400)
        d.shot("click_translated")

    if sc in ("all", "screen"):
        d.key(Qt.Key_Return)
        d.pump(30)
        d.shot("screen_pending")
        ok = d.wait_until(d.translation_done)
        d.pump(500)
        d.shot("screen_translated" if ok else "screen_timeout")
        d.key(Qt.Key_Space, release=False)
        d.pump(250)
        d.shot("space_original")
        d.key(Qt.Key_Space)
        d.pump(250)
        # copy one block
        first = d.ov._ordered_items()[0]
        d.click(first.block.rect.cx, first.block.rect.cy)
        d.pump(250)
        d.shot("copied_toast")
        print("clipboard:", QGuiApplication.clipboard().text()[:80])
        d.ov._toggle_menu()
        d.pump(200)
        d.shot("lang_menu")

    if sc == "empty":
        d.drag(lasso_around(type("R", (), {"cx": 900, "cy": 1150, "w": 40, "h": 20})(), 10))
        d.pump(300)
        d.shot("no_text")

    d.key(Qt.Key_Escape)
    d.pump(50)
    print("state after Esc:", d.ov.state)
    d.engine.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
