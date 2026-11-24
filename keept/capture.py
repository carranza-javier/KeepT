"""Screen capture of the monitor under the cursor, in physical pixels."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

import numpy as np

from .platform import MonitorInfo, services

log = logging.getLogger(__name__)


@dataclass
class Capture:
    monitor: MonitorInfo
    bgra: np.ndarray  # (height, width, 4) uint8, physical pixels of the monitor
    taken_at: float = field(default_factory=time.perf_counter)

    @property
    def width(self) -> int:
        return int(self.bgra.shape[1])

    @property
    def height(self) -> int:
        return int(self.bgra.shape[0])


class ScreenGrabber:
    """Keeps an mss instance per thread (mss holds thread bound GDI handles)."""

    def __init__(self) -> None:
        self._local = threading.local()

    def _mss(self):
        inst = getattr(self._local, "mss", None)
        if inst is None:
            import mss

            factory = getattr(mss, "MSS", None) or mss.mss
            inst = factory()
            self._local.mss = inst
        return inst

    def grab(self, monitor: MonitorInfo) -> Capture:
        region = {"left": monitor.left, "top": monitor.top, "width": monitor.width, "height": monitor.height}
        shot = self._mss().grab(region)
        arr = np.frombuffer(shot.raw, dtype=np.uint8).reshape(shot.height, shot.width, 4)
        return Capture(monitor, arr)

    def grab_cursor_monitor(self) -> Capture:
        return self.grab(services().monitor_at_cursor())

    def close(self) -> None:
        inst = getattr(self._local, "mss", None)
        if inst is not None:
            inst.close()
            self._local.mss = None
