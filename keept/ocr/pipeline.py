"""Read a whole screen: OCR, grouping into blocks and per block language detection."""

from __future__ import annotations

import logging
import statistics
import time
from collections import Counter
from dataclasses import dataclass

import numpy as np

from ..translate.langdetect import detect
from . import OcrBackend
from .cleanup import clean, merge_readings
from .layout import Block, Line, Rect, Word, group_lines

log = logging.getLogger(__name__)

SMALL_TEXT_PX = 11.0  # median line height (physical px) below which we OCR at 2x only
# Lines up to this height are also read at 2x and both readings are merged: at 1x the OCR
# reads periods of body text as "_" and drops small words, at 2x it loses some umlauts.
BODY_TEXT_PX = 18.0


@dataclass
class ScreenText:
    blocks: list[Block]
    screen_lang: str | None
    timings: dict[str, float]
    engine_lang: str = "en"
    scale: float = 1.0
    both: bool = False  # read at 1x and 2x and merged


def _regions(rects: list[Rect], gap: float) -> list[Rect]:
    """Rectangles merged into regions: two rects closer than `gap` end up in the same one."""
    regions = [r.adjusted(-gap / 2, -gap / 2, gap / 2, gap / 2) for r in rects]
    merged = True
    while merged:
        merged = False
        out: list[Rect] = []
        for r in regions:
            for i, o in enumerate(out):
                if o.intersection_area(r) > 0:
                    out[i] = o.union(r)
                    merged = True
                    break
            else:
                out.append(r)
        regions = out
    return regions


def read_lines(ocr: OcrBackend, bgra: np.ndarray, lang: str, scale: float, both: bool,
               first: list[Line] | None = None) -> list[Line]:
    """OCR lines of an image: at `scale`, or with the small text also read at 2x and merged
    when `both`. Only the regions with small lines are read again, which keeps the cost low
    on screens with little small text."""
    if not both:
        return first if first is not None and scale == 1.0 else ocr.recognize(bgra, lang, scale=scale)
    lines1 = first if first is not None else ocr.recognize(bgra, lang)
    small = [l for l in lines1 if l.height < BODY_TEXT_PX]
    if not small:
        return lines1
    big = [l.rect for l in lines1 if l.height >= BODY_TEXT_PX]
    lines2: list[Line] = []
    h = statistics.median(l.height for l in small)
    H, W = bgra.shape[:2]
    # Wide margins left and right: the 1x reading may have missed small text next to the
    # lines it found (an e-mail address in a grey header line).
    for region in _regions([l.rect.adjusted(-8 * h, 0, 8 * h, 0) for l in small], gap=h * 3):
        crop, dx, dy = _crop(bgra, region, h)
        if crop.size == 0:
            continue
        ch, cw = crop.shape[:2]
        for line in _offset(ocr.recognize(crop, lang, scale=2.0), dx, dy):
            r = line.rect
            # A line cut by the crop border is read again whole by the 1x pass.
            cut = (r.x - dx < 2 and dx > 0) or (dx + cw - r.right < 2 and dx + cw < W)                 or (r.y - dy < 1 and dy > 0) or (dy + ch - r.bottom < 1 and dy + ch < H)
            # Bigger text that the region happens to touch keeps its 1x reading.
            if not cut and not any(b.intersection_area(r) > 0.3 * r.w * r.h for b in big):
                lines2.append(line)
    return merge_readings(lines2, lines1)


def _crop(bgra: np.ndarray, r: Rect, pad: float) -> tuple[np.ndarray, float, float]:
    h, w = bgra.shape[:2]
    x0, y0 = max(0, int(r.x - pad)), max(0, int(r.y - pad))
    x1, y1 = min(w, int(r.right + pad + 1)), min(h, int(r.bottom + pad + 1))
    return np.ascontiguousarray(bgra[y0:y1, x0:x1]), x0, y0


def _offset(lines: list[Line], dx: float, dy: float) -> list[Line]:
    return [Line([Word(wd.text, Rect(wd.rect.x + dx, wd.rect.y + dy, wd.rect.w, wd.rect.h)) for wd in l.words]) for l in lines]


LONG_WORDS = 6  # blocks with at least this many words decide which languages a screen has
MIXED_SHARE = 0.15  # a language with this share of the long text makes the screen multilingual


def detect_languages(blocks: list[Block], fallback: str) -> None:
    """Language of every block. On a screen in one language, short labels keep the screen
    language unless another one is clearly more likely. On a multilingual screen (a letter in
    German, French and Italian) every block is judged on its own, among the languages of the
    screen, so "Cordiali saluti" stays Italian next to a French paragraph."""
    from ..translate.langdetect import scores

    screen_lang, _ = detect(" ".join(b.text for b in blocks))
    present = Counter()
    for b in blocks:
        if len(b.text.split()) >= LONG_WORDS:
            present[detect(b.text)[0]] += len(b.text)
    total = sum(present.values())
    langs = {l for l, w in present.items() if l and w >= MIXED_SHARE * total}
    for b in blocks:
        if len(langs) >= 2:
            if len(b.text.split()) >= LONG_WORDS:
                b.lang = detect(b.text)[0] or screen_lang or fallback
            else:
                probs = scores(b.text) if any(c.isalpha() for c in b.text) else {}
                cand = {l: p for l, p in probs.items() if l in langs}
                b.lang = max(cand, key=cand.get) if cand else (screen_lang or fallback)
        else:
            b.lang = detect(b.text, prior=screen_lang)[0] or screen_lang or fallback


def first_pass(ocr: OcrBackend, bgra: np.ndarray, hint_lang: str) -> ScreenText:
    """Full screen OCR with one engine, grouping and language detection. Fast (~100-250 ms)."""
    timings: dict[str, float] = {}
    available = ocr.available_languages()
    if not available:
        raise RuntimeError("no OCR language installed")
    lang = hint_lang if hint_lang in available else ("en" if "en" in available else available[0])

    t0 = time.perf_counter()
    lines = ocr.recognize(bgra, lang)
    scale, both = 1.0, False
    if lines and max(bgra.shape[:2]) * 2 <= 10000:
        median_h = statistics.median(l.height for l in lines)
        if median_h < SMALL_TEXT_PX:
            scale = 2.0
            lines = ocr.recognize(bgra, lang, scale=2.0)
        elif any(l.height < BODY_TEXT_PX for l in lines):
            both = True
            lines = read_lines(ocr, bgra, lang, 1.0, True, first=lines)
    lines = clean(lines, bgra)
    timings["ocr"] = time.perf_counter() - t0

    t1 = time.perf_counter()
    blocks = group_lines(lines)
    timings["layout"] = time.perf_counter() - t1

    detect_languages(blocks, lang)
    screen_lang = None
    if blocks:
        weights = Counter()
        for b in blocks:
            weights[b.lang] += len(b.text)
        screen_lang = weights.most_common(1)[0][0]
    log.info("OCR %s x%s: %d lines, %d blocks, screen=%s | ocr %.0f ms, layout %.0f ms",
             lang, "1+2" if both else f"{scale:.0f}", len(lines), len(blocks), screen_lang, timings["ocr"] * 1000, timings["layout"] * 1000)
    st = ScreenText(blocks, screen_lang, timings)
    st.engine_lang = lang
    st.scale = scale
    st.both = both
    return st


def needs_reread(block, engine_lang: str, available) -> bool:
    # English has no accents, so an English block read by another Latin engine is fine.
    return (block.lang != engine_lang and block.lang in available and block.lang != "en"
            and len(block.text) >= 3)


def _inside(lines: list[Line], block: Block) -> list[Line]:
    """Words of a re-read crop that belong to the block (the crop has a margin that may catch
    a neighbour), with the box of the first reading where both found the word: the boxes of a
    padded crop read at 2x are a little larger, which would change the font size estimate."""
    area = block.rect.adjusted(*(d * block.line_height * 0.3 for d in (-1, -1, 1, 1)))
    old = [w for l in block.lines for w in l.words]
    out = []
    for line in lines:
        words = []
        for w in line.words:
            if not area.contains(w.rect.cx, w.rect.cy):
                continue
            match = max(old, key=lambda o: o.rect.intersection_area(w.rect), default=None)
            if match is not None and match.rect.intersection_area(w.rect) > 0.5 * min(w.rect.w * w.rect.h, match.rect.w * match.rect.h):
                w = Word(w.text, match.rect)
            words.append(w)
        if words:
            out.append(Line(words, inline=line.inline))
    return out


def refine(ocr: OcrBackend, bgra: np.ndarray, st: ScreenText, alive=lambda: True) -> dict[int, list[Line]]:
    """Read again, with the matching engine, the crops of blocks in another language than the
    first pass engine (fixes accents such as ó read as ö). Returns new lines per block id."""
    t0 = time.perf_counter()
    available = ocr.available_languages()
    out: dict[int, list[Line]] = {}
    for b in st.blocks:
        if not alive():
            break
        if not needs_reread(b, st.engine_lang, available):
            continue
        # A tight crop makes the OCR miss words at 1x and inflate the boxes at 2x.
        pad = max(b.line_height * 1.2, 20.0)
        crop, dx, dy = _crop(bgra, b.rect, pad)
        if crop.size == 0:
            continue
        try:
            new_lines = read_lines(ocr, crop, b.lang, st.scale, st.both)
        except Exception as exc:  # noqa: BLE001 - keep the first reading
            log.debug("Re-OCR failed: %s", exc)
            continue
        if not new_lines:
            continue
        regrouped = group_lines(_inside(clean(_offset(new_lines, dx, dy), bgra), b))
        if len(regrouped) == 1 and len(regrouped[0].lines) == len(b.lines) and regrouped[0].text != b.text:
            out[b.id] = regrouped[0].lines
    st.timings["reread"] = time.perf_counter() - t0
    log.info("OCR refine: %d block(s) re-read in %.0f ms", len(out), st.timings["reread"] * 1000)
    return out


def read_screen(ocr: OcrBackend, bgra: np.ndarray, hint_lang: str) -> ScreenText:
    """First pass plus refinement, synchronously (tools and selftest)."""
    st = first_pass(ocr, bgra, hint_lang)
    new = refine(ocr, bgra, st)
    for b in st.blocks:
        if b.id in new:
            b.lines = new[b.id]
    return st
