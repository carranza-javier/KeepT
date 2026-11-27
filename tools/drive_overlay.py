"""Drive the real overlay with synthetic input and save frames, to review it visually.

Works without touching the real mouse/keyboard (events are posted to the widget),
so it also runs while the Windows session is locked.

    python tools/drive_overlay.py shots/test150.png --out shots/run --scenario all

Timing as in the app (engines warmed up and models loaded before the hotkey):

    python tools/drive_overlay.py screen.png --warm de,fr,it,en --scenario timing --pick "Ab dem"

"Translate screen" (Enter) on the whole page, first and last block:

    python tools/drive_overlay.py screen.png --warm de,fr,it,en --scenario page
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

    _touch = None

    @classmethod
    def touch_device(cls):
        """A touch screen device: mouse events from it are what Windows sends for a finger."""
        if cls._touch is None:
            from PySide6.QtGui import QInputDevice, QPointingDevice

            cls._touch = QPointingDevice("synthetic touchscreen", 4242, QInputDevice.DeviceType.TouchScreen,
                                         QPointingDevice.PointerType.Finger, QInputDevice.Capability.Position, 1, 0)
        return cls._touch

    def _mouse(self, kind, pos: QPointF, button, buttons, touch: bool = False) -> None:
        extra = (self.touch_device(),) if touch else ()
        ev = QMouseEvent(kind, pos, self.ov.mapToGlobal(pos), button, buttons, Qt.NoModifier, *extra)
        QApplication.sendEvent(self.ov, ev)

    def drag(self, points_phys, shot_mid: str | None = None, touch: bool = False) -> None:
        """Mouse drag (rectangle) or, with touch=True, a finger drag (lasso)."""
        pts = [self.phys_to_logical(x, y) for x, y in points_phys]
        self._mouse(QEvent.MouseButtonPress, pts[0], Qt.LeftButton, Qt.LeftButton, touch)
        for i, p in enumerate(pts[1:], 1):
            self._mouse(QEvent.MouseMove, p, Qt.NoButton, Qt.LeftButton, touch)
            self.pump(4)
            if shot_mid and i == int(len(pts) * 0.85):
                self.pump(20)
                self.shot(shot_mid)
        self._mouse(QEvent.MouseButtonRelease, pts[-1], Qt.LeftButton, Qt.NoButton, touch)

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
    ap.add_argument("--warm", help="source languages: warm up OCR and load their models first, as the app does")
    ap.add_argument("--pick", default="", help="text a block starts with, for the click and rect timings")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--warm-cache", action="store_true",
                    help="keep OCR and translation caches between runs (the same screen opened again)")
    ap.add_argument("--frames", action="store_true", help="page: save frames while the blocks appear")
    ap.add_argument("--wait", type=float, default=0.3,
                    help="page: seconds between the end of the OCR and Enter (-1: Enter right after the hotkey)")
    args = ap.parse_args()

    services().init_process()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1])  # noqa: F841
    i18n.set_ui_lang(services().system_language())
    d = Driver(args.image, Path(args.out), args.dark, args.target, args.device, args.debug_blocks)
    sc = args.scenario

    if args.warm:
        sources = args.warm.split(",")
        d.engine.warm_up(sources[0])
        d.ov.warm_up()
        d.engine.preload(args.target, download=False, sources=sources)
        from keept.translate.translator import route

        need = {p for src in sources for p in route(src, args.target)}
        d.wait_until(lambda: need <= set(d.engine.translator.loaded_pairs()), 60000)
        d.pump(1500)  # warm up and preload run on worker threads

    if sc == "timing":
        return timing(d, args)
    if sc == "page":
        return page(d, args)

    d.open()
    d.pump(110)
    d.shot("entry_110ms")
    d.pump(600)
    d.shot("ready")
    d.wait_until(lambda: d.ov.ocr_done, 5000)
    print("blocks:", [(b.id, b.lang, b.text[:30]) for b in d.ov.blocks])

    if sc in ("all", "lasso"):
        target = d.ov.blocks[min(2, len(d.ov.blocks) - 1)]
        d.drag(lasso_around(target.rect), shot_mid="lasso_drawing", touch=True)
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
        d.drag(lasso_around(type("R", (), {"cx": 900, "cy": 1150, "w": 40, "h": 20})(), 10), touch=True)
        d.pump(300)
        d.shot("no_text")

    d.key(Qt.Key_Escape)
    d.pump(50)
    print("state after Esc:", d.ov.state)
    d.engine.shutdown()
    return 0


def clear_caches(d: "Driver", args) -> None:
    """Every run starts from scratch, unless --warm-cache (the same screen opened again)."""
    if getattr(args, "warm_cache", False):
        return
    from keept.ocr.recognizer import clear_cache

    d.engine.translator.clear_cache()
    clear_cache()


def timing(d: "Driver", args) -> int:
    """Time from the request to the first translated block on screen, for a click on a block (the
    pointer rests on it 250 ms before), a rectangle drawn around it in 300 ms and Enter pressed
    right after the hotkey (OCR not finished yet). The user looks at the screen 300 ms first."""
    results: dict[str, list[float]] = {}

    def first_done_ms(t0: float) -> float | None:
        ok = d.wait_until(lambda: any(i.status == "done" for i in d.ov.items.values()), 60000)
        return (time.perf_counter() - t0) * 1000 if ok else None

    def find_block():
        return next(b for b in d.ov.blocks if b.text.startswith(args.pick)) if args.pick else d.ov.blocks[len(d.ov.blocks) // 2]

    for run in range(args.runs):
        for kind in ("click", "rect", "enter_now"):
            clear_caches(d, args)
            t_hotkey = time.perf_counter()
            d.ov.open(d.capture, t_hotkey)
            if kind == "enter_now":
                d.pump(30)
                t0 = time.perf_counter()
                d.key(Qt.Key_Return)
            else:
                d.wait_until(lambda: d.ov.ocr_done, 10000)
                d.pump(300)  # the user needs a moment to aim
                b = find_block()
                if kind == "click":
                    # The pointer reaches the block, then the click comes about 250 ms later.
                    d._mouse(QEvent.MouseMove, d.phys_to_logical(b.rect.x + 5, b.rect.cy), Qt.NoButton, Qt.NoButton)
                    d.pump(250)
                    t0 = time.perf_counter()
                    d.click(b.rect.x + 5, b.rect.cy)
                else:
                    # A rectangle drawn around the block in about 300 ms; timed from the release.
                    r = b.rect
                    pts = [d.phys_to_logical(r.x - 10 + i * (r.w + 20) / 10, r.y - 8 + i * (r.h + 16) / 10) for i in range(11)]
                    d._mouse(QEvent.MouseButtonPress, pts[0], Qt.LeftButton, Qt.LeftButton)
                    for pt in pts[1:]:
                        d._mouse(QEvent.MouseMove, pt, Qt.NoButton, Qt.LeftButton)
                        d.pump(30)
                    t0 = time.perf_counter()
                    d._mouse(QEvent.MouseButtonRelease, pts[-1], Qt.LeftButton, Qt.NoButton)
            ms = first_done_ms(t0)
            hot = (time.perf_counter() - t_hotkey) * 1000
            results.setdefault(kind, []).append(ms or -1)
            print(f"run {run} {kind:9s}: first block {ms:.0f} ms after the request, {hot:.0f} ms after the hotkey", flush=True)
            if run == 0:
                d.wait_until(d.translation_done, 60000)
                d.pump(400)
                d.shot(f"timing_{kind}")
            d.key(Qt.Key_Escape)
            d.pump(300)
    for kind, values in results.items():
        values.sort()
        print(f"{kind:9s}: median {values[len(values) // 2]:.0f} ms, all {[round(v) for v in values]}")
    d.engine.shutdown()
    return 0


def page(d: "Driver", args) -> int:
    """"Translate screen" (Enter) on the whole page once its OCR is done: time to the first
    translated block and to the last one, and the order in which the languages appear."""
    for run in range(args.runs):
        clear_caches(d, args)
        d.ov.open(d.capture, time.perf_counter())
        if args.wait < 0:
            d.pump(30)  # Enter right after the hotkey, before the OCR is done
        else:
            d.wait_until(lambda: d.ov.ocr_done, 10000)
            d.pump(args.wait * 1000)
        t0 = time.perf_counter()
        d.key(Qt.Key_Return)
        first = None
        order: list[str] = []
        seen: set[int] = set()
        shots: list[int] = []
        while time.perf_counter() - t0 < 60:
            QApplication.processEvents()
            for k, it in d.ov.items.items():
                if it.status == "done" and k not in seen:
                    seen.add(k)
                    order.append(it.block.lang or "?")
                    first = first or time.perf_counter() - t0
            if run == 0 and args.frames and len(shots) < 4 and time.perf_counter() - t0 > 0.08 * (len(shots) + 1) + (first or 9):
                shots.append(1)
                d.shot(f"wave_{len(shots)}")
            if d.translation_done():
                break
            time.sleep(0.002)
        total = time.perf_counter() - t0
        import builtins  # timeline of reads and translations, filled by an instrumenting wrapper

        for a, b, *rest in sorted(getattr(builtins, "KEEPT_EV", [])):
            if b >= t0:
                print(f"   {(a - t0) * 1000:6.0f} {(b - t0) * 1000:6.0f}", *rest)
        getattr(builtins, "KEEPT_EV", []).clear()
        # The page is fully visible when the last block has been uncovered.
        from keept.overlay.overlay_window import REVEAL_MS

        end = max((it.t_done for it in d.ov.items.values() if it.status == "done"), default=d.ov.now())
        if end + REVEAL_MS > d.ov.now():
            d.pump(end + REVEAL_MS - d.ov.now())
        visible = time.perf_counter() - t0
        print(f"run {run} page: first block {first * 1000:.0f} ms, all {len(seen)} blocks {total * 1000:.0f} ms,"
              f" whole page visible {visible * 1000:.0f} ms, order {''.join(l[0] for l in order)}", flush=True)
        if run == 0:
            d.pump(400)
            d.shot("page")
        d.key(Qt.Key_Escape)
        d.pump(300)
    d.engine.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
