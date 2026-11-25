"""Run by test_overlay_geometry.py in a subprocess with QT_SCALE_FACTOR set (100/125/150 %).

Checks that a click in logical coordinates hits the right block (physical coordinates)
and that the translated box is painted exactly over the original physical pixels.
Prints "OK" on success.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PySide6.QtCore import QEvent, QObject, QPointF, Qt, Signal  # noqa: E402
from PySide6.QtGui import QGuiApplication, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from keept.capture import Capture  # noqa: E402
from keept.ocr.layout import Block, Line, Rect, Word  # noqa: E402
from keept.ocr.pipeline import ScreenText  # noqa: E402
from keept.overlay.overlay_window import OverlayWindow  # noqa: E402
from keept.platform import MonitorInfo  # noqa: E402


class StubEngine(QObject):
    ocr_finished = Signal(int, object)
    ocr_failed = Signal(int, str)
    ocr_refined = Signal(int, object)
    progress = Signal(int, str, float)
    translated = Signal(int, int, str)
    translation_finished = Signal(int, float)
    translation_failed = Signal(int, str, object)

    def __init__(self):
        super().__init__()
        self.jobs = []

    def set_active(self, s):
        pass

    def start_ocr(self, *a):
        pass

    def translate(self, session, jobs, tgt):
        self.jobs.append((session, jobs, tgt))


def pump(ms):
    end = time.perf_counter() + ms / 1000
    while time.perf_counter() < end:
        QApplication.processEvents()
        time.sleep(0.005)


def main() -> int:
    app = QApplication(sys.argv[:1])  # noqa: F841
    screen = QGuiApplication.primaryScreen()
    dpr = screen.devicePixelRatio()
    expected = float(os.environ["QT_SCALE_FACTOR"])
    assert abs(dpr - expected) < 1e-6, (dpr, expected)
    g = screen.geometry()
    W, H = round(g.width() * dpr), round(g.height() * dpr)

    bgra = np.full((H, W, 4), 255, np.uint8)
    # two "text" blocks, dark ink on white, at known physical rects
    rects = [Rect(101, 77, 180, 23), Rect(400, 301, 120, 21)]
    for r in rects:
        for x in range(int(r.x) + 2, int(r.right) - 2, 5):
            bgra[int(r.y) + 3:int(r.bottom) - 3, x:x + 2, :3] = 30
    blocks = [Block([Line([Word("Hello world", r)])], id=i, lang="en") for i, r in enumerate(rects)]

    engine = StubEngine()
    ov = OverlayWindow(engine, "es", dark=False)
    cap = Capture(MonitorInfo("x", g.x(), g.y(), W, H, dpr), bgra)
    ov.open(cap, time.perf_counter())
    assert abs(ov.scale - dpr) < 1e-6, ov.scale
    ov._on_ocr_finished(ov.session, ScreenText(blocks, "en", {}))

    # click the centre of the second block, in logical coordinates
    target = rects[1]
    pos = QPointF(target.cx / dpr, target.cy / dpr)
    for kind, button, buttons in ((QEvent.MouseButtonPress, Qt.LeftButton, Qt.LeftButton),
                                  (QEvent.MouseButtonRelease, Qt.LeftButton, Qt.NoButton)):
        QApplication.sendEvent(ov, QMouseEvent(kind, pos, ov.mapToGlobal(pos), button, buttons, Qt.NoModifier))
    assert len(engine.jobs) == 1, engine.jobs
    (_, jobs, tgt) = engine.jobs[0]
    assert [j.key for j in jobs] == [1] and tgt == "es"

    # Short text: the offscreen platform has no fonts and draws one box per glyph.
    ov._on_translated(ov.session, 1, "Hi")
    ov._on_translation_finished(ov.session, 0.1)
    pump(500)
    img = ov.grab().toImage()
    assert (img.width(), img.height()) == (W, H), (img.width(), img.height(), W, H)

    def ink(r: Rect) -> int:
        dark = 0
        for y in range(int(r.y) + 4, int(r.bottom) - 4, 2):
            for x in range(int(r.x) + 3, int(r.right) - 3, 2):
                c = img.pixelColor(x, y)
                dark += c.red() < 120
        return dark

    # The original ink of block 1 is covered: the right part of the box (beyond the short
    # translated word) must now be clean background, exactly within the block.
    right_half = Rect(target.x + target.w * 0.6, target.y, target.w * 0.4, target.h)
    assert ink(right_half) == 0, "original text still visible under the translation"
    # Block 0 was not translated: its ink is intact.
    assert ink(rects[0]) > 20, "untranslated block was painted over"
    # Just outside the covered area nothing changed.
    c = img.pixelColor(int(target.right + 12), int(target.cy))
    assert c.red() > 240, c.name()
    # A block in a language whose Windows OCR pack is missing is reported (once per request).
    from keept.ocr import backend as ocr_backend

    reported = []
    ov.ocr_pack_missing.connect(reported.append)
    missing = next(c for c in ("pl", "nl", "it", "pt", "fr") if c not in ocr_backend().available_languages())
    ov.translate_blocks([Block([Line([Word("Zapisz zmiany", Rect(700, 500, 120, 21))])], id=50, lang=missing)])
    ov.translate_blocks([Block([Line([Word("Save changes", Rect(700, 560, 120, 21))])], id=51, lang="en")])
    assert reported == [missing], reported
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
