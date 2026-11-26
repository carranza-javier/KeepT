"""Fixes for systematic mistakes of the OCR engine.

Windows OCR reads small body text (lines of about 15 physical pixels, the usual size at 100 %
scaling) with two recurring mistakes:
- the period, a dot of one or two pixels on the baseline, comes out as "_" ("1 _ Dezember",
  "lunedi_", "7_00_"). Read at 2x the periods are right, but some umlauts are lost ("Säcke"
  becomes "Sacke"). So small text is read at both scales and the readings are merged word by
  word (`merge_readings`), and leftover "_" that stand for a period are fixed (`fix_periods`).
- a raised ordinal sign ("1°", "1º") is read as a zero ("10 dicembre"); `fix_degree` looks at
  the pixels of the last glyph to tell them apart.
"""

from __future__ import annotations

import re
import unicodedata

import numpy as np

from .layout import Line, Rect, Word


def _base(text: str) -> str:
    """Letters and digits without accents, lower case."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if c.isalnum()).lower()


def _marks(text: str) -> int:
    return sum(1 for c in unicodedata.normalize("NFD", text) if unicodedata.combining(c))


def _overlap(a: Rect, b: Rect) -> float:
    inter = a.intersection_area(b)
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union > 0 else 0.0


def merge_readings(primary: list[Line], secondary: list[Line]) -> list[Line]:
    """`primary` (read at 2x: punctuation, small words) with the accents of `secondary` (read at
    1x) where both read the same letters; lines only `secondary` found are added."""
    sec_words = [w for l in secondary for w in l.words]
    out: list[Line] = []
    for line in primary:
        words = []
        for w in line.words:
            best, best_ov = None, 0.3
            for s in sec_words:
                ov = _overlap(w.rect, s.rect)
                if ov > best_ov:
                    best, best_ov = s, ov
            text, rect = w.text, w.rect
            if best is not None:
                # The 1x box is tighter (the 2x upscale blurs every glyph edge by about a pixel),
                # which matters for the font size estimate of small text.
                rect = best.rect
                if _base(best.text) and _base(best.text) == _base(w.text) and _marks(best.text) > _marks(w.text):
                    # Same letters, more accents: take the letters of the 1x reading, keep the
                    # punctuation of the 2x one ("Säcke" + "Sacke." -> "Säcke.").
                    text = _with_letters(w.text, best.text)
            words.append(Word(text, rect))
        out.append(Line(words))
    for line in secondary:
        r = line.rect
        if not any(_overlap(r, p.rect) > 0.1 or p.rect.intersection_area(r) > 0.3 * r.w * r.h for p in primary):
            out.append(line)
            continue
        # Words only the 1x reading found ("À" of "À partir") go into the 2x line they belong to.
        for w in line.words:
            if any(w.rect.intersection_area(p.rect) > 0 for l in primary for p in l.words):
                continue
            for i, l in enumerate(out):
                lr = l.rect
                v = min(lr.bottom, w.rect.bottom) - max(lr.y, w.rect.y)
                if v > 0.5 * min(lr.h, w.rect.h) and lr.x - 2 * lr.h <= w.rect.cx <= lr.right + 2 * lr.h:
                    out[i] = Line(sorted([*l.words, w], key=lambda x: x.rect.x))
                    break
    return out


def _with_letters(target: str, source: str) -> str:
    """`target` with its alphanumeric characters replaced, in order, by those of `source`."""
    letters = [c for c in unicodedata.normalize("NFC", source) if c.isalnum()]
    out, i = [], 0
    for c in target:
        if c.isalnum() and i < len(letters):
            out.append(letters[i])
            i += 1
        else:
            out.append(c)
    return "".join(out)


_DIGIT_US_DIGIT = re.compile(r"(?<=\d)_(?=\d)")
_TRAILING_US = re.compile(r"(?<=[^\W_])_$")


def fix_periods(lines: list[Line]) -> list[Line]:
    """"_" that stands for a period: a lone "_" right after a word, "_" between digits and a
    single "_" at the end of a word. Identifiers ("snake_case", "__init__") are left alone."""
    out = []
    for line in lines:
        words: list[Word] = []
        for w in line.words:
            text = w.text
            if set(text) == {"_"} and len(text) == 1 and words:
                prev = words[-1]
                if not prev.text.endswith((".", "_")) and w.rect.x - prev.rect.right < max(prev.rect.h, 1.0):
                    words[-1] = Word(prev.text + ".", prev.rect.union(w.rect))
                    continue
            if "_" in text and not text.startswith("_"):
                fixed = _DIGIT_US_DIGIT.sub(".", text)
                if fixed.count("_") == 1:
                    fixed = _TRAILING_US.sub(".", fixed)
                text = fixed
            words.append(Word(text, w.rect))
        out.append(Line(words, inline=line.inline))
    return out


_ORDINAL_ZERO = re.compile(r"^(\d{1,2})[0oO]$")


def _glyph_runs(ink: np.ndarray) -> list[tuple[int, int]]:
    cols = ink.any(axis=0)
    runs, start = [], None
    for x, on in enumerate(cols):
        if on and start is None:
            start = x
        elif not on and start is not None:
            runs.append((start, x))
            start = None
    if start is not None:
        runs.append((start, len(cols)))
    return runs


def raised_last_glyph(bgra: np.ndarray, rect: Rect) -> bool:
    """True when the last glyph of the word sits clearly above the baseline (°, º, ª)."""
    h, w = bgra.shape[:2]
    x0, y0 = max(0, int(rect.x)), max(0, int(rect.y))
    x1, y1 = min(w, int(np.ceil(rect.right)) + 1), min(h, int(np.ceil(rect.bottom)) + 1)
    if x1 - x0 < 3 or y1 - y0 < 5:
        return False
    crop = bgra[y0:y1, x0:x1, :3].astype(np.int16)
    border = np.concatenate([crop[0], crop[-1], crop[:, 0], crop[:, -1]])
    bg = np.median(border, axis=0)
    diff = np.abs(crop - bg).sum(axis=2)
    if diff.max() < 90:
        return False
    ink = diff > diff.max() * 0.45
    runs = _glyph_runs(ink)
    if len(runs) < 2:
        return False
    rows = lambda a, b: np.nonzero(ink[:, a:b].any(axis=1))[0]  # noqa: E731
    first = np.concatenate([rows(a, b) for a, b in runs[:-1]])
    last = rows(*runs[-1])
    if len(first) == 0 or len(last) == 0:
        return False
    top, base = first.min(), first.max()
    return last.max() < top + 0.6 * (base - top)


def fix_degree(lines: list[Line], bgra: np.ndarray | None) -> list[Line]:
    """"10" read from "1°": put the ordinal sign back when the last glyph is raised."""
    if bgra is None:
        return lines
    out = []
    for line in lines:
        words = []
        for w in line.words:
            m = _ORDINAL_ZERO.match(w.text)
            if m and raised_last_glyph(bgra, w.rect):
                w = Word(m.group(1) + "°", w.rect)
            words.append(w)
        out.append(Line(words, inline=line.inline))
    return out


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
        if len(words) < 3:
            out.append(line)
            continue
        gaps = [b.rect.x - a.rect.right for a, b in zip(words, words[1:])]
        typical = float(np.median(gaps))
        r = line.rect
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


_FRENCH_MONTHS = {"janvier", "février", "fevrier", "mars", "avril", "mai", "juin", "juillet", "août", "aout",
                  "septembre", "octobre", "novembre", "décembre", "decembre"}


def fix_first(lines: list[Line]) -> list[Line]:
    """"1er décembre" read as "ler décembre" or "Ier décembre" (l, I and 1 look alike)."""
    out = []
    for line in lines:
        words = list(line.words)
        for i, w in enumerate(words[:-1]):
            if w.text in ("ler", "Ier", "1er") and words[i + 1].text.lower().strip(".,") in _FRENCH_MONTHS:
                words[i] = Word("1er", w.rect)
        out.append(Line(words, inline=line.inline))
    return out


def clean(lines: list[Line], bgra: np.ndarray | None = None) -> list[Line]:
    return mark_separators(fix_first(fix_degree(fix_periods(lines), bgra)), bgra)
