"""Geometry types for OCR output and grouping of lines into blocks.

All coordinates are physical pixels of the captured monitor image.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px <= self.right and self.y <= py <= self.bottom

    def union(self, other: "Rect") -> "Rect":
        x, y = min(self.x, other.x), min(self.y, other.y)
        return Rect(x, y, max(self.right, other.right) - x, max(self.bottom, other.bottom) - y)

    def adjusted(self, dx1: float, dy1: float, dx2: float, dy2: float) -> "Rect":
        return Rect(self.x + dx1, self.y + dy1, self.w - dx1 + dx2, self.h - dy1 + dy2)

    def scaled(self, factor: float) -> "Rect":
        return Rect(self.x * factor, self.y * factor, self.w * factor, self.h * factor)

    def intersection_area(self, other: "Rect") -> float:
        w = min(self.right, other.right) - max(self.x, other.x)
        h = min(self.bottom, other.bottom) - max(self.y, other.y)
        return w * h if w > 0 and h > 0 else 0.0

    @staticmethod
    def bounding(rects) -> "Rect":
        rects = list(rects)
        out = rects[0]
        for r in rects[1:]:
            out = out.union(r)
        return out


@dataclass
class Word:
    text: str
    rect: Rect


# Glyph classes (Segoe UI like proportions, in em): descenders go ~0.21 below the
# baseline, ascenders and capitals reach ~0.74 above it, x-height is ~0.5.
_DESCENDERS = set("gjpqyQ,;()[]{}|@ç")
_ASCENDERS = set("bdfhklt0123456789?!/\'\"%&#()[]{}|ß") | set("áéíóúäöüñ")
DESC_EM, ASC_EM, X_EM = 0.21, 0.74, 0.52


@dataclass
class Line:
    words: list[Word]
    # Part of a line that was cut at a separator ("Grüsse • salutations • saluti"): such parts
    # are separate items and never join the lines above or below.
    inline: bool = False

    @property
    def rect(self) -> Rect:
        return Rect.bounding(w.rect for w in self.words)

    def metrics(self) -> tuple[float, float]:
        """(em size, baseline y) estimated from the line box and the kind of glyphs it contains."""
        text = self.text
        r = self.rect
        desc = any(c in _DESCENDERS for c in text)
        asc = any(c.isupper() or c in _ASCENDERS for c in text)
        if desc and asc:
            em = r.h / (ASC_EM + DESC_EM)
        elif desc:
            em = r.h / (X_EM + DESC_EM)
        elif asc:
            em = r.h / ASC_EM
        else:
            em = r.h / X_EM
        baseline = r.bottom - (DESC_EM * em if desc else 0.0)
        return em, baseline

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def height(self) -> float:
        """Height of the line box (ascenders to descenders)."""
        return self.rect.h

    @property
    def is_caps(self) -> bool:
        """An all capitals label ("FRANÇAIS", "ENGLISH")."""
        letters = [c for c in self.text if c.isalpha()]
        return len(letters) >= 3 and all(c.isupper() for c in letters)


@dataclass
class Block:
    lines: list[Line]
    id: int = 0
    lang: str = ""  # detected source language
    meta: dict = field(default_factory=dict)

    @property
    def rect(self) -> Rect:
        return Rect.bounding(l.rect for l in self.lines)

    @property
    def text(self) -> str:
        return join_lines([l.text for l in self.lines])

    @property
    def line_height(self) -> float:
        return statistics.median(l.height for l in self.lines)

    @property
    def font_px(self) -> float:
        """Estimated font pixel size (em) of the original text."""
        return statistics.median(l.metrics()[0] for l in self.lines)

    @property
    def baseline(self) -> float:
        """Baseline of the first line."""
        return self.lines[0].metrics()[1]

    def cover_rect(self) -> Rect:
        """Area to paint over: the text box with a small margin so no glyph edge peeks out."""
        pad = max(2.0, self.line_height * 0.18)
        return self.rect.adjusted(-pad, -pad, pad, pad)


_HYPHEN_END = re.compile(r"[A-Za-zÄÖÜäöüßÑñÁÉÍÓÚáéíóú]-$")


def join_lines(lines: list[str]) -> str:
    """Join OCR lines of one block into running text, undoing end of line hyphenation."""
    out = ""
    for text in lines:
        text = text.strip()
        if not text:
            continue
        if not out:
            out = text
        elif _HYPHEN_END.search(out) and text[:1].islower():
            out = out[:-1] + text
        else:
            out += " " + text
    return out


SEPARATORS = {"•", "·", "|", "◦", "‧", "∙", "●", "▪"}


def split_line_on_gaps(line: Line, gap_factor: float = 1.8) -> list[Line]:
    """Split an OCR line where a horizontal gap is much larger than the text height (columns,
    table cells) and at separators ("Grüsse • salutations"; cleanup.mark_separators adds the
    ones the OCR did not read)."""
    words = sorted(line.words, key=lambda w: w.rect.x)
    if not words:
        return []
    h = statistics.median(w.rect.h for w in words)
    parts: list[list[Word]] = [[]]
    inline = [False]

    def cut(as_item: bool) -> None:
        if as_item:
            inline[-1] = True  # both sides of a separator are items
        parts.append([])
        inline.append(as_item)

    for i, w in enumerate(words):
        if w.text.strip() in SEPARATORS:
            # Between words it separates items; at the start of a line it is a list bullet.
            later = any(x.text.strip() not in SEPARATORS for x in words[i + 1:])
            if parts[-1] and later:
                cut(True)
            continue
        if parts[-1] and i > 0:
            gap = w.rect.x - words[i - 1].rect.right
            if gap > gap_factor * h:
                cut(False)
        parts[-1].append(w)
    return [Line(p, inline=bool(f)) for p, f in zip(parts, inline) if p]


_SENTENCE_END = re.compile(r"[.!?…:]\W*$")


def _can_join(block: Block, line: Line) -> tuple[bool, float]:
    last = block.lines[-1]
    if line.inline or last.inline:
        return False, 0.0
    if line.is_caps != last.is_caps:
        return False, 0.0  # a label in capitals is never part of the paragraph next to it
    lr, br, cr = last.rect, block.rect, line.rect
    h_ref = max(last.height, 1.0)
    ratio = line.height / h_ref
    if not 0.7 <= ratio <= 1.45:
        return False, 0.0
    h = max(last.height, line.height)
    vgap = cr.y - lr.bottom
    if vgap < -0.4 * h or vgap > 0.95 * h:
        return False, 0.0
    # Paragraph break: a clearly bigger gap than between the lines of the block so far, or, for
    # a single line that ends a sentence, a gap of half a line.
    if len(block.lines) >= 2:
        inner = statistics.median(b.rect.y - a.rect.bottom for a, b in zip(block.lines, block.lines[1:]))
        if vgap > inner + max(3.0, 0.35 * h):
            return False, 0.0
    elif _SENTENCE_END.search(last.text) and vgap > 0.5 * h:
        return False, 0.0
    overlap = min(br.right, cr.right) - max(br.x, cr.x)
    if overlap <= 0:
        return False, 0.0
    tol = 1.5 * h
    left = abs(cr.x - br.x) <= tol
    center = abs(cr.cx - br.cx) <= tol
    right = abs(cr.right - br.right) <= tol
    if not (left or center or right):
        return False, 0.0
    return True, vgap


def group_lines(lines: list[Line]) -> list[Block]:
    """Group lines into blocks (paragraphs, buttons, cells) by vertical proximity,
    horizontal alignment and similar text height."""
    segments: list[Line] = []
    for line in lines:
        if line.words:
            segments.extend(split_line_on_gaps(line))
    segments.sort(key=lambda l: (l.rect.y, l.rect.x))
    blocks: list[Block] = []
    for line in segments:
        best: Block | None = None
        best_gap = float("inf")
        for block in blocks:
            ok, gap = _can_join(block, line)
            if ok and gap < best_gap:
                best, best_gap = block, gap
        if best is None:
            blocks.append(Block([line]))
        else:
            best.lines.append(line)
    blocks.sort(key=lambda b: (round(b.rect.y / 8), b.rect.x))
    for i, b in enumerate(blocks):
        b.id = i
    return blocks
