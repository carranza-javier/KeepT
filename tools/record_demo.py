"""Record frames of the real overlay on the synthetic test screen, for the README animation.

    python tools/record_demo.py shots/test150.png shots/demo_frames
Then build the GIF with tools/make_gif.py (needs Pillow, a development only dependency).
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drive_overlay import Driver  # noqa: E402
from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from keept import i18n  # noqa: E402
from keept.platform import services  # noqa: E402


def main() -> int:
    services().init_process()
    app = QApplication(sys.argv[:1])  # noqa: F841
    i18n.set_ui_lang("en")
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    d = Driver(sys.argv[1], out, False, "es", None, False)
    d.engine.preload("es", download=False, sources=("de", "en"))
    n = 0

    def frame(hold_ms: int = 60) -> None:
        nonlocal n
        img = d.ov.grab().toImage()
        img.save(str(out / f"{n:03d}_{hold_ms}.png"))
        n += 1

    def film(ms: int, step: int = 60) -> None:
        end = time.perf_counter() + ms / 1000
        while time.perf_counter() < end:
            d.pump(step)
            frame(step)

    frame(700)  # the plain screen before the shortcut
    d.open()
    film(700)  # glow entry and pill
    d.wait_until(lambda: d.ov.ocr_done, 5000)
    # drag a rectangle over the German paragraph with the mouse
    target = d.ov.blocks[2].rect
    x0, y0 = target.x - 30, target.y - 25
    x1, y1 = target.x + target.w + 30, target.y + target.h + 25
    steps = 22
    pts = [d.phys_to_logical(x0 + (x1 - x0) * k / steps, y0 + (y1 - y0) * (k / steps) ** 0.9) for k in range(steps + 1)]
    d._mouse(QEvent.MouseButtonPress, pts[0], Qt.LeftButton, Qt.LeftButton)
    for i, p in enumerate(pts[1:], 1):
        d._mouse(QEvent.MouseMove, p, Qt.NoButton, Qt.LeftButton)
        d.pump(12)
        if i % 2 == 0:
            frame(50)
    frame(250)
    d._mouse(QEvent.MouseButtonRelease, pts[-1], Qt.LeftButton, Qt.NoButton)
    film(450, 75)  # shimmer and the translation fading in
    d.wait_until(d.translation_done, 20000)
    film(300, 100)
    frame(1400)
    d.key(Qt.Key_Return)  # translate everything
    film(900, 90)
    d.wait_until(d.translation_done, 20000)
    d.pump(300)
    frame(2600)
    d.key(Qt.Key_Escape)
    d.engine.shutdown()
    print("frames:", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
