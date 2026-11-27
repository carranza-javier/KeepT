"""Separators the OCR did not read or misread.

Windows OCR drops small middle dots between items ("Fiktives Beispieldokument · Fictitious
sample document") or reads them as a hyphen, which would join two items in different
languages into one block. The pixels tell whether there was a separator: in an unusually wide
word gap, or in the box of a lone "-" (a dot is about as wide as tall, a hyphen much wider).
"""

from __future__ import annotations

import numpy as np

from .layout import Line, Rect, Word


def _gap_ink(bgra: np.ndarray, x0: float, x1: float, y0: float, y1: float) -> tuple[float, float] | None:
    """(height, vertical centre) of the ink between two words, relative to the line box, or None
    when the gap is empty."""
    h, w = bgra.shape[:2]
    a, b = max(0, int(np.ceil(x0)) + 1), min(w, int(x1) - 1)
    c, d = max(0, int(y0)), min(h, int(np.ceil(y1)) + 1)
    if b - a < 2 or d - c < 4:
        return None
    crop = bgra[c:d, a:b, :3].astype(np.int16)
    border = np.concatenate([crop[0], crop[-1]])
    bg = np.median(border, axis=0)
    diff = np.abs(crop - bg).sum(axis=2)
    if diff.max() < 90:
        return None
    rows = np.nonzero((diff > diff.max() * 0.45).any(axis=1))[0]
    if len(rows) == 0:
        return None
    return (rows.max() - rows.min() + 1) / (d - c), (rows.min() + rows.max()) / 2 / (d - c)


_DOT_LIKE = {"-", "–", "·", "."}


def _is_dot(bgra: np.ndarray, word: Rect, line: Rect) -> bool:
    """True when the ink in the box of a one character word is a dot, not a dash."""
    h, w = bgra.shape[:2]
    a, b = max(0, int(word.x) - 1), min(w, int(np.ceil(word.right)) + 2)
    c, d = max(0, int(line.y)), min(h, int(np.ceil(line.bottom)) + 1)
    if b - a < 2 or d - c < 4:
        return False
    crop = bgra[c:d, a:b, :3].astype(np.int16)
    bg = np.median(np.concatenate([crop[0], crop[-1]]), axis=0)
    diff = np.abs(crop - bg).sum(axis=2)
    if diff.max() < 90:
        return False
    ys, xs = np.nonzero(diff > diff.max() * 0.45)
    ink_w, ink_h = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    centre = (ys.min() + ys.max()) / 2 / (d - c)
    return ink_w <= ink_h + 1 and ink_h <= 0.35 * (d - c) and 0.25 <= centre <= 0.8


def mark_separators(lines: list[Line], bgra: np.ndarray | None) -> list[Line]:
    """Add the separators the OCR did not read ("Fiktives Beispieldokument · Fictitious sample
    document" read without the dot). A gap much wider than the other word gaps of the line is a
    separator when it holds a small dot or nothing; when it holds something tall, the OCR
    dropped a word ("au plus tard à 7 h" read without "à") and the line stays whole."""
    if bgra is None:
        return lines
    out = []
    for line in lines:
        words = sorted(line.words, key=lambda w: w.rect.x)
        r = line.rect
        words = [Word("•", w.rect) if 0 < i < len(words) - 1 and w.text in _DOT_LIKE and _is_dot(bgra, w.rect, r) else w
                 for i, w in enumerate(words)]
        if len(words) < 3:
            out.append(Line(words, inline=line.inline))
            continue
        gaps = [b.rect.x - a.rect.right for a, b in zip(words, words[1:])]
        typical = float(np.median(gaps))
        new: list[Word] = [words[0]]
        for prev, cur, gap in zip(words, words[1:], gaps):
            if gap > max(0.6 * r.h, 2.2 * typical) and gap <= 1.8 * r.h:
                ink = _gap_ink(bgra, prev.rect.right, cur.rect.x, r.y, r.bottom)
                if ink is None or (ink[0] <= 0.35 and 0.25 <= ink[1] <= 0.8):
                    x = prev.rect.right + 1
                    new.append(Word("•", Rect(x, r.cy - 1, max(1.0, cur.rect.x - x - 1), 2)))
            new.append(cur)
        out.append(Line(new, inline=line.inline))
    return out
