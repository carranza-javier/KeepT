"""Overlay rendering helpers: background and text colour sampling, text fitting, painting.

Sampling and fitting are pure functions (numpy / an injected measure function)
so they can be unit tested without a screen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np

from ..ocr.layout import Rect

RGB = tuple[int, int, int]


# -- colours ------------------------------------------------------------------
def _clip_box(shape, x0: float, y0: float, x1: float, y1: float) -> tuple[int, int, int, int] | None:
    h, w = shape[:2]
    a, b = max(0, int(math.floor(x0))), max(0, int(math.floor(y0)))
    c, d = min(w, int(math.ceil(x1))), min(h, int(math.ceil(y1)))
    if c <= a or d <= b:
        return None
    return a, b, c, d


def _rgb_pixels(bgra: np.ndarray, box) -> np.ndarray:
    a, b, c, d = box
    return bgra[b:d, a:c, 2::-1].reshape(-1, 3)  # BGR(A) -> RGB


def ring_pixels(bgra: np.ndarray, rect: Rect, gap: float = 2.0, thickness: float = 3.0) -> np.ndarray:
    """RGB pixels in a ring just outside `rect`."""
    outer = rect.adjusted(-gap - thickness, -gap - thickness, gap + thickness, gap + thickness)
    inner = rect.adjusted(-gap, -gap, gap, gap)
    strips = [
        (outer.x, outer.y, outer.right, inner.y),  # top
        (outer.x, inner.bottom, outer.right, outer.bottom),  # bottom
        (outer.x, inner.y, inner.x, inner.bottom),  # left
        (inner.right, inner.y, outer.right, inner.bottom),  # right
    ]
    parts = []
    for s in strips:
        box = _clip_box(bgra.shape, *s)
        if box:
            parts.append(_rgb_pixels(bgra, box))
    if not parts:
        return np.zeros((0, 3), np.uint8)
    return np.concatenate(parts)


def sample_background(bgra: np.ndarray, rect: Rect) -> RGB:
    """Median colour of the border around a text block."""
    px = ring_pixels(bgra, rect)
    if len(px) == 0:
        box = _clip_box(bgra.shape, rect.x, rect.y, rect.right, rect.bottom)
        if box is None:
            return (255, 255, 255)
        px = _rgb_pixels(bgra, box)
    med = np.median(px, axis=0)
    return int(med[0]), int(med[1]), int(med[2])


def luminance(c: RGB) -> float:
    def ch(v: float) -> float:
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = c
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_ratio(a: RGB, b: RGB) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


DARK_TEXT: RGB = (28, 28, 30)
LIGHT_TEXT: RGB = (250, 250, 250)


def contrast_text(bg: RGB) -> RGB:
    return DARK_TEXT if contrast_ratio(bg, DARK_TEXT) >= contrast_ratio(bg, LIGHT_TEXT) else LIGHT_TEXT


def sample_text_color(bgra: np.ndarray, rect: Rect, bg: RGB) -> RGB:
    """Colour of the original glyphs: the pixels inside the block that differ most from the background.
    Falls back to plain dark/light text when that colour would be hard to read."""
    box = _clip_box(bgra.shape, rect.x, rect.y, rect.right, rect.bottom)
    if box is None:
        return contrast_text(bg)
    px = _rgb_pixels(bgra, box).astype(np.int32)
    dist = np.abs(px - np.array(bg, np.int32)).sum(axis=1)
    if len(dist) == 0 or dist.max() < 60:
        return contrast_text(bg)
    cutoff = np.percentile(dist, 92)
    ink = px[dist >= max(cutoff, 60)]
    med = np.median(ink, axis=0)
    color = (int(med[0]), int(med[1]), int(med[2]))
    if contrast_ratio(color, bg) < 3.0:
        return contrast_text(bg)
    return color


def is_boxed(bgra: np.ndarray, rect: Rect, bg: RGB, line_height: float) -> bool:
    """True when the text sits on its own small box (a button or a chip): the colour a bit
    further above AND below the text differs from the immediate background."""
    off = line_height * 1.1
    verdicts = []
    for y0, y1 in ((rect.y - off - 3, rect.y - off), (rect.bottom + off, rect.bottom + off + 3)):
        box = _clip_box(bgra.shape, rect.x, y0, rect.right, y1)
        if box:
            med = np.median(_rgb_pixels(bgra, box), axis=0)
            verdicts.append(float(np.abs(med - np.array(bg)).sum()) > 45)
    return bool(verdicts) and all(verdicts)


def free_space_right(bgra: np.ndarray, rect: Rect, bg: RGB, max_px: float) -> float:
    """How far (px) the background continues to the right of `rect` without other content.
    Stops at text, borders or any change of background colour."""
    x0 = int(math.ceil(rect.right)) + 1
    box = _clip_box(bgra.shape, x0, rect.y, x0 + max_px, rect.bottom)
    if box is None:
        return 0.0
    px = _rgb_pixels(bgra, box).reshape(box[3] - box[1], box[2] - box[0], 3).astype(np.int16)
    differs = np.abs(px - np.array(bg, np.int16)).sum(axis=2) > 40
    busy = np.nonzero(differs.mean(axis=0) > 0.02)[0]
    return float(busy[0]) if len(busy) else float(box[2] - box[0])


def stroke_ratio(bgra: np.ndarray, rect: Rect, bg: RGB, fg: RGB, em: float) -> float:
    """Average horizontal stroke width of the glyphs divided by the font size.
    Anti-aliased coverage is counted fractionally, so it works for small text too."""
    box = _clip_box(bgra.shape, rect.x, rect.y, rect.right, rect.bottom)
    if box is None or em <= 0:
        return 0.0
    a, b, c, d = box
    px = bgra[b:d, a:c, 2::-1].astype(np.float32)
    bg_a, fg_a = np.array(bg, np.float32), np.array(fg, np.float32)
    span = float(np.abs(fg_a - bg_a).sum())
    if span < 60:
        return 0.0
    cover = np.clip(np.abs(px - bg_a).sum(axis=2) / span, 0.0, 1.0)
    ink = cover > 0.5
    starts = int((ink[:, 1:] & ~ink[:, :-1]).sum() + ink[:, 0].sum())
    if starts == 0:
        return 0.0
    # Anti-aliasing widens every stroke by roughly 0.3 px whatever the size.
    return max(0.0, float(cover.sum()) / starts - 0.3) / em


def weight_class(ratio: float) -> int:
    """0 = regular, 1 = semibold, 2 = bold."""
    if ratio < 0.115:
        return 0
    if ratio < 0.16:
        return 1
    return 2


# -- text fitting -------------------------------------------------------------
Measure = Callable[[str, float], float]  # (text, pixel size) -> width


@dataclass
class FitResult:
    px: float
    lines: list[str]
    line_height: float
    height: float  # total text height
    box_height: float  # background height (>= original when it had to grow)


def wrap(text: str, width: float, px: float, measure: Measure) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}" if current else word
        if measure(candidate, px) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
        # A single word wider than the box is split by characters.
        while measure(current, px) > width and len(current) > 1:
            cut = len(current) - 1
            while cut > 1 and measure(current[:cut], px) > width:
                cut -= 1
            lines.append(current[:cut])
            current = current[cut:]
    if current:
        lines.append(current)
    return lines


def fit_text(
    text: str,
    width: float,
    height: float,
    start_px: float,
    min_px: float,
    measure: Measure,
    line_spacing: float = 1.25,
    max_grow: float = 1.6,
) -> FitResult:
    """Find a font size so the wrapped text fits the block.

    1. Shrink from the original size down to a comfortable floor (65 % of it).
    2. If it still does not fit, let the background grow down (up to `max_grow`).
    3. Then keep shrinking down to the minimum legible size.
    4. At the minimum size, grow the background as much as needed.
    """
    start_px = max(start_px, min_px)
    soft_floor = max(min_px, start_px * 0.65)
    step = max(0.5, start_px * 0.04)

    def attempt(px: float) -> tuple[list[str], float]:
        lines = wrap(text, width, px, measure)
        return lines, len(lines) * px * line_spacing

    def result(px: float, lines: list[str], needed: float) -> FitResult:
        return FitResult(px, lines, px * line_spacing, needed, max(height, needed))

    px = start_px
    while px >= soft_floor:
        lines, needed = attempt(px)
        if needed <= height * 1.02:
            return result(px, lines, needed)
        px -= step
    px = soft_floor
    while px >= min_px:
        lines, needed = attempt(px)
        if needed <= height * max_grow:
            return result(px, lines, needed)
        px -= step
    lines, needed = attempt(min_px)
    return result(min_px, lines, needed)
