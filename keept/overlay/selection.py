"""Turn a pointer gesture into a selection of text blocks.

A gesture is a list of points in physical pixels. It is classified as:
- click: the pointer barely moved,
- rect: an almost straight diagonal stroke (the two ends are opposite corners),
- lasso: anything else (the stroke is closed implicitly).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..ocr.layout import Block, Line, Rect

Point = tuple[float, float]


@dataclass(frozen=True)
class Gesture:
    kind: str  # "click" | "rect" | "lasso"
    points: tuple[Point, ...]
    rect: Rect | None = None


def path_length(points: list[Point]) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def _max_deviation(points: list[Point]) -> float:
    (x1, y1), (x2, y2) = points[0], points[-1]
    d = math.hypot(x2 - x1, y2 - y1)
    if d == 0:
        return max((math.dist(points[0], p) for p in points), default=0.0)
    return max(abs((x2 - x1) * (y1 - py) - (x1 - px) * (y2 - y1)) / d for px, py in points)


def classify(points: list[Point], click_tolerance: float = 6.0) -> Gesture:
    if not points:
        raise ValueError("empty gesture")
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    if max(xs) - min(xs) <= click_tolerance and max(ys) - min(ys) <= click_tolerance:
        return Gesture("click", (points[0],))
    start, end = points[0], points[-1]
    d = math.dist(start, end)
    dx, dy = abs(end[0] - start[0]), abs(end[1] - start[1])
    if d > 3 * click_tolerance and dx > click_tolerance and dy > click_tolerance:
        straight = path_length(points) / d < 1.15 and _max_deviation(points) < 0.12 * d
        if straight:
            r = Rect(min(start[0], end[0]), min(start[1], end[1]), dx, dy)
            return Gesture("rect", tuple(points), r)
    return Gesture("lasso", tuple(points))


def point_in_polygon(x: float, y: float, poly: tuple[Point, ...] | list[Point]) -> bool:
    inside = False
    n = len(poly)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def block_at(blocks: list[Block], x: float, y: float) -> Block | None:
    """The block under a point (smallest one if several overlap)."""
    hits = [b for b in blocks if b.cover_rect().contains(x, y)]
    if not hits:
        return None
    return min(hits, key=lambda b: b.rect.w * b.rect.h)


def _line_in_rect(line: Line, r: Rect) -> bool:
    lr = line.rect
    if r.contains(lr.cx, lr.cy):
        return True
    area = lr.w * lr.h
    return area > 0 and lr.intersection_area(r) >= 0.5 * area


def _line_in_lasso(line: Line, poly: tuple[Point, ...]) -> bool:
    lr = line.rect
    if point_in_polygon(lr.cx, lr.cy, poly):
        return True
    centers = [point_in_polygon(w.rect.cx, w.rect.cy, poly) for w in line.words]
    return sum(centers) * 2 >= len(centers)


def _line_touched(line: Line, points: tuple[Point, ...], pad: float) -> bool:
    r = line.rect.adjusted(-pad, -pad, pad, pad)
    return any(r.contains(x, y) for x, y in points)


def _subset(block: Block, keep: list[bool]) -> Block | None:
    if not any(keep):
        return None
    if all(keep):
        return block
    idx = [i for i, k in enumerate(keep) if k]
    part = Block([block.lines[i] for i in idx], id=block.id * 1000 + idx[0] + 1, lang=block.lang)
    part.meta["parent"] = block.id
    return part


def select_blocks(blocks: list[Block], gesture: Gesture) -> list[Block]:
    """Blocks (or the selected lines of a block) covered by the gesture, in reading order."""
    if gesture.kind == "click":
        b = block_at(blocks, *gesture.points[0])
        return [b] if b else []
    chosen: list[Block] = []
    for block in blocks:
        if gesture.kind == "rect":
            keep = [_line_in_rect(l, gesture.rect) for l in block.lines]
        else:
            keep = [_line_in_lasso(l, gesture.points) for l in block.lines]
        part = _subset(block, keep)
        if part:
            chosen.append(part)
    if not chosen and gesture.kind == "lasso":
        # An open stroke (for example underlining a line) encloses nothing: use what it touches.
        for block in blocks:
            pad = block.line_height * 0.3
            part = _subset(block, [_line_touched(l, gesture.points, pad) for l in block.lines])
            if part:
                chosen.append(part)
    return chosen
