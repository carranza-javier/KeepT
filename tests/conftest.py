import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keept.ocr.layout import Line, Rect, Word  # noqa: E402


def make_line(text: str, x: float, y: float, h: float = 20.0, char_w: float = 10.0) -> Line:
    """A synthetic OCR line: words laid out left to right with one char of spacing."""
    words = []
    cx = x
    for token in text.split():
        w = len(token) * char_w
        words.append(Word(token, Rect(cx, y, w, h)))
        cx += w + char_w
    return Line(words)
