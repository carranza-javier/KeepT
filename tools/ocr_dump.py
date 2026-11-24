"""Print the blocks KeepT reads from an image: python tools/ocr_dump.py image.png [hint_lang]"""
import sys

import numpy as np
from PySide6.QtGui import QImage

from keept.ocr import backend
from keept.ocr.pipeline import read_screen


def load_bgra(path: str) -> np.ndarray:
    img = QImage(path).convertToFormat(QImage.Format_RGB32)
    arr = np.frombuffer(img.constBits(), np.uint8, img.sizeInBytes())
    return arr.reshape(img.height(), img.bytesPerLine() // 4, 4)[:, : img.width()].copy()


if __name__ == "__main__":
    st = read_screen(backend(), load_bgra(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "en")
    for b in st.blocks:
        r = b.rect
        print(f"#{b.id:<2} {b.lang} [{r.x:.0f},{r.y:.0f} {r.w:.0f}x{r.h:.0f}] font~{b.font_px:.0f} lines={len(b.lines)}: {b.text}")
