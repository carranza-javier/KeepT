"""Second reading of the text lines Windows OCR found, with the PP-OCRv5 latin recognizer.

Windows OCR finds lines and their boxes quickly and reliably, but misreads many characters
in small, grey or dense text: periods become "_", umlauts and accents get lost or swapped
("puö", "Ä partir"), "1°" becomes "10". The PP-OCRv5 latin recognizer (PaddleOCR, Apache
2.0, 7.9 MB) reads one cropped line at a time and gets almost all of them right (research:
99 % of the words of the test set, 81 % for Windows OCR alone on umlauts and accents).

It runs on onnxruntime with plain numpy pre and post processing (no OpenCV).
"""

from __future__ import annotations

import logging
import math
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .layout import Rect

log = logging.getLogger(__name__)

MODEL = Path(__file__).with_name("latin_PP-OCRv5_rec_mobile.onnx")
HEIGHT = 48  # input height of the model
MIN_RATIO = 320 / 48  # the model was trained on inputs at least this wide
BATCH = 1  # measured: padding lines of a batch to the widest one costs more than it saves
THREADS = 4


@dataclass
class Reading:
    text: str
    confidence: float  # mean probability of the characters, 0..1
    # Horizontal centre of every character of `text`, in image pixels (spaces included).
    char_x: list[float]


def _resize(bgra: np.ndarray, nh: int, nw: int) -> np.ndarray:
    """Smooth (bilinear) resize of a BGRA crop to nh x nw, as float32 BGR. Qt does it in C++
    and QImage is safe to use off the UI thread."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage

    h, w = bgra.shape[:2]
    src = np.ascontiguousarray(bgra)
    img = QImage(src.data, w, h, w * 4, QImage.Format_RGB32)
    out = img.scaled(nw, nh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_RGB32)
    arr = np.frombuffer(out.constBits(), np.uint8, out.sizeInBytes())
    return arr.reshape(nh, out.bytesPerLine() // 4, 4)[:, :nw, :3].astype(np.float32)


class LineRecognizer:
    """Thread safe: onnxruntime sessions can run from several threads at once."""

    def __init__(self, path: Path = MODEL, threads: int = THREADS) -> None:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        opts.log_severity_level = 3
        self._session = ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])
        self._input = self._session.get_inputs()[0].name
        chars = self._session.get_modelmeta().custom_metadata_map["character"].splitlines()
        # CTC: index 0 is the blank, the space comes last.
        self._chars = ["", *chars, " "]

    def read(self, bgra: np.ndarray, rects: list[Rect]) -> list[Reading]:
        """Read the text of every rectangle (a line found by Windows OCR) of the image."""
        h, w = bgra.shape[:2]
        crops: list[tuple[np.ndarray, float]] = []
        for r in rects:
            pad = max(2, int(r.h * 0.25))
            x0, y0 = max(0, int(r.x) - pad), max(0, int(r.y) - pad)
            x1, y1 = min(w, int(math.ceil(r.right)) + pad), min(h, int(math.ceil(r.bottom)) + pad)
            crops.append((bgra[y0:y1, x0:x1], float(x0)))
        out: list[Reading | None] = [None] * len(crops)
        order = sorted(range(len(crops)), key=lambda i: crops[i][0].shape[1] / max(1, crops[i][0].shape[0]))
        for start in range(0, len(order), BATCH):
            ids = [i for i in order[start:start + BATCH] if crops[i][0].size]
            for i in order[start:start + BATCH]:
                if not crops[i][0].size:
                    out[i] = Reading("", 0.0, [])
            if ids:
                for i, reading in zip(ids, self._run([crops[i] for i in ids])):
                    out[i] = reading
        return [r or Reading("", 0.0, []) for r in out]

    def _run(self, crops: list[tuple[np.ndarray, float]]) -> list[Reading]:
        ratios = [c.shape[1] / c.shape[0] for c, _ in crops]
        width = int(HEIGHT * max(MIN_RATIO, *ratios))
        batch = np.zeros((len(crops), 3, HEIGHT, width), np.float32)
        scales = []
        for k, (crop, _) in enumerate(crops):
            rw = min(width, int(math.ceil(HEIGHT * ratios[k])))
            img = _resize(crop, HEIGHT, rw) / 255.0
            batch[k, :, :, :rw] = (img.transpose(2, 0, 1) - 0.5) / 0.5
            scales.append(crop.shape[1] / rw)
        preds = self._session.run(None, {self._input: batch})[0]  # (N, T, classes)
        step = width / preds.shape[1]
        idx = preds.argmax(axis=2)
        prob = preds.max(axis=2)
        out = []
        for k, (_, x0) in enumerate(crops):
            text, confs, xs = [], [], []
            prev = 0
            for t, c in enumerate(idx[k]):
                if c != 0 and c != prev and c < len(self._chars):
                    text.append(self._chars[c])
                    confs.append(float(prob[k, t]))
                    xs.append(x0 + (t + 0.5) * step * scales[k])
                prev = c
            out.append(Reading("".join(text), float(np.mean(confs)) if confs else 0.0, xs))
        return out


_rec: LineRecognizer | None = None
_failed = False
_lock = threading.Lock()


_single: LineRecognizer | None = None


def recognizer(single_thread: bool = False) -> LineRecognizer | None:
    """The shared recognizer, or None if it cannot run (then Windows OCR text is used).
    `single_thread`: a second session with one thread, for the threads that read several
    lines at once (four sessions of four threads each overload a laptop CPU)."""
    global _rec, _single, _failed
    with _lock:
        if _rec is None and not _failed:
            try:
                _rec = LineRecognizer()
            except Exception as exc:  # noqa: BLE001 - fall back to the Windows OCR text
                log.warning("Line recognizer unavailable, using Windows OCR text: %s", exc)
                _failed = True
        if single_thread and _rec is not None:
            if _single is None:
                try:
                    _single = LineRecognizer(threads=1)
                except Exception:  # noqa: BLE001 - share the main one
                    _single = _rec
            return _single
        return _rec
