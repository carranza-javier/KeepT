"""Time to first translated block with released models, in process and with exact delays.

Same code path as the hotkey: release models, start the background reload, open the overlay
(OCR starts), press Enter after `delay` seconds, wait for the first translated block.
    python tools/time_reload_inproc.py shots/test150.png es 0.15 0.3 0.6 1.0 1.5
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drive_overlay import Driver  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from keept.platform import services  # noqa: E402

import logging

logging.basicConfig(level=logging.INFO, format="%(relativeCreated)7.0f %(name)s: %(message)s")
services().init_process()
app = QApplication(sys.argv[:1])
image, target, delays = sys.argv[1], sys.argv[2], [float(x) for x in sys.argv[3:]]
d = Driver(image, Path("shots/timing"), False, target, None, False)
eng = d.engine


def flush():
    import threading

    ev = threading.Event()
    eng._tr_pool.submit(ev.set)
    while not ev.is_set():
        app.processEvents()
        time.sleep(0.005)


def first_block_time(t_hotkey):
    while True:
        app.processEvents()
        done = [it for it in d.ov.items.values() if it.status == "done"]
        if done:
            return time.perf_counter() - t_hotkey
        time.sleep(0.002)


rows = []
for label, delay, release in [("warm", 0.6, False)] + [(f"cold {x:.2f}s", x, True) for x in delays]:
    eng.preload(target, download=False)
    flush()
    if release:
        eng.release_models()
        flush()
    t0 = time.perf_counter()
    eng.reload_models(target, "de")  # what the hotkey does first
    d.ov.open(d.capture, t0)
    d.pump(delay * 1000)
    t_req = time.perf_counter()
    d.key(Qt.Key_Return)
    t = first_block_time(t0)
    rows.append((label, delay, t * 1000, (t0 + t - t_req) * 1000))
    d.wait_until(d.translation_done, 20000)
    d.key(Qt.Key_Escape)
    d.pump(200)
for label, delay, after_hotkey, after_enter in rows:
    print(f"{label:11s} Enter at {delay*1000:5.0f} ms -> first block {after_hotkey:5.0f} ms after hotkey, "
          f"{after_enter:5.0f} ms after Enter")
eng.shutdown()
