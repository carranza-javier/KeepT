"""Turn a pointer gesture into a selection of text blocks.

The kind of selection depends only on the input device, never on the shape of the stroke:
- a press that barely moves is a click (or a tap) on a block,
- dragging with a mouse (or touchpad) selects a rectangle between the press and release points,
- dragging with a finger or a pen draws a free-hand lasso.
Points are in physical pixels.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ocr.layout import Block, Line, Rect

Point = tuple[float, float]


@dataclass(frozen=True)
class Gesture:
    kind: str  # "click" | "rect" | "lasso"
    points: tuple[Point, ...]
    rect: Rect | None = None


def drag_rect(start: Point, end: Point) -> Rect:
    return Rect(min(start[0], end[0]), min(start[1], end[1]), abs(end[0] - start[0]), abs(end[1] - start[1]))


def classify(points: list[Point], tool: str = "mouse", click_tolerance: float = 6.0) -> Gesture:
    """`tool` is "mouse" (mouse or touchpad) or "touch" (finger or pen)."""
    if not points:
        raise ValueError("empty gesture")
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    if max(xs) - min(xs) <= click_tolerance and max(ys) - min(ys) <= click_tolerance:
        return Gesture("click", (points[0],))
    if tool == "mouse":
        return Gesture("rect", (points[0], points[-1]), drag_rect(points[0], points[-1]))
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
    if not chosen:
        # An open stroke or a very flat rectangle (for example underlining a line) encloses
        # nothing: use the lines it touches.
        for block in blocks:
            pad = block.line_height * 0.3
            if gesture.kind == "lasso":
                keep = [_line_touched(l, gesture.points, pad) for l in block.lines]
            else:
                grown = gesture.rect.adjusted(-pad, -pad, pad, pad)
                keep = [l.rect.intersection_area(grown) > 0 for l in block.lines]
            part = _subset(block, keep)
            if part:
                chosen.append(part)
    return chosen
