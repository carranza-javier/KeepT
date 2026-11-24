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
from .layout import Block, Line, Rect, Word, group_lines

log = logging.getLogger(__name__)

SMALL_TEXT_PX = 11.0  # median line height (physical px) below which we OCR at 2x


@dataclass
class ScreenText:
    blocks: list[Block]
    screen_lang: str | None
    timings: dict[str, float]


def _crop(bgra: np.ndarray, r: Rect, pad: float) -> tuple[np.ndarray, float, float]:
    h, w = bgra.shape[:2]
    x0, y0 = max(0, int(r.x - pad)), max(0, int(r.y - pad))
    x1, y1 = min(w, int(r.right + pad + 1)), min(h, int(r.bottom + pad + 1))
    return np.ascontiguousarray(bgra[y0:y1, x0:x1]), x0, y0


def _offset(lines: list[Line], dx: float, dy: float) -> list[Line]:
    return [Line([Word(wd.text, Rect(wd.rect.x + dx, wd.rect.y + dy, wd.rect.w, wd.rect.h)) for wd in l.words]) for l in lines]


def read_screen(ocr: OcrBackend, bgra: np.ndarray, hint_lang: str) -> ScreenText:
    timings: dict[str, float] = {}
    available = ocr.available_languages()
    if not available:
        raise RuntimeError("no OCR language installed")
    lang = hint_lang if hint_lang in available else ("en" if "en" in available else available[0])

    t0 = time.perf_counter()
    lines = ocr.recognize(bgra, lang)
    scale = 1.0
    if lines:
        median_h = statistics.median(l.height for l in lines)
        if median_h < SMALL_TEXT_PX and max(bgra.shape[:2]) * 2 <= 10000:
            scale = 2.0
            lines = ocr.recognize(bgra, lang, scale=2.0)
    timings["ocr"] = time.perf_counter() - t0

    t1 = time.perf_counter()
    blocks = group_lines(lines)
    timings["layout"] = time.perf_counter() - t1

    # Language of the whole screen first (more text, more reliable), then per block with it as prior.
    screen_lang, _ = detect(" ".join(b.text for b in blocks))
    for b in blocks:
        b.lang = detect(b.text, prior=screen_lang)[0] or screen_lang or lang
    if blocks:
        weights = Counter()
        for b in blocks:
            weights[b.lang] += len(b.text)
        screen_lang = weights.most_common(1)[0][0]

    # Blocks in another language than the engine we used are read again with the right
    # engine (only the crop), which fixes accents such as ó read as ö.
    t2 = time.perf_counter()
    reread = 0
    for b in blocks:
        if b.lang != lang and b.lang in available and len(b.text) >= 3:
            pad = b.line_height * 0.6
            crop, dx, dy = _crop(bgra, b.rect, pad)
            if crop.size == 0:
                continue
            try:
                new_lines = ocr.recognize(crop, b.lang, scale=scale)
            except Exception as exc:  # noqa: BLE001 - keep the first reading
                log.debug("Re-OCR failed: %s", exc)
                continue
            if not new_lines:
                continue
            new_lines = _offset(new_lines, dx, dy)
            regrouped = group_lines(new_lines)
            if len(regrouped) == 1 and len(regrouped[0].lines) == len(b.lines):
                b.lines = regrouped[0].lines
                reread += 1
    timings["reread"] = time.perf_counter() - t2
    log.info(
        "OCR %s x%.0f: %d lines, %d blocks, screen=%s, reread=%d | ocr %.0f ms, layout %.0f ms, reread %.0f ms",
        lang, scale, len(lines), len(blocks), screen_lang, reread,
        timings["ocr"] * 1000, timings["layout"] * 1000, timings["reread"] * 1000,
    )
    return ScreenText(blocks, screen_lang, timings)
