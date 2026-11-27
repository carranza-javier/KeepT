"""Read a whole screen: Windows OCR finds the lines, they are grouped into blocks, every block
gets a language, and the PP-OCRv5 latin recognizer reads the text of the lines again.

The Windows reading is fast (~100-250 ms for a screen) and gives the layout at once; the second
reading (~60 ms per line) fixes its character mistakes. It runs block by block, the blocks the
user asks to translate first (see Engine), so the first translation does not wait for the
whole screen.
"""

from __future__ import annotations

import logging
import re
import statistics
import time
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from ..translate.langdetect import detect
from . import OcrBackend
from .cleanup import mark_separators
from .layout import SEPARATORS, Block, Line, Rect, Word, group_lines

log = logging.getLogger(__name__)

SMALL_TEXT_PX = 11.0  # median line height (physical px) below which Windows OCR reads at 2x
# With lines up to this height on the screen, Windows OCR also looks for lines at 2x: at 1x it
# misses some small grey text entirely (an e-mail address in a 9 pt letter head). Only what it
# did not find at 1x is added; the text of every line is read by the line recognizer anyway.
FIND_SMALL_PX = 18.0
# A block whose second reading is less sure than this is not translated (icons, noise,
# decorative fonts): a wrong translation painted over the screen is worse than none. Measured
# on the test set and 12 full web pages: real text scores 0.82 or more (775 blocks).
LOW_CONFIDENCE = 0.70


@dataclass
class ScreenText:
    blocks: list[Block]
    screen_lang: str | None
    timings: dict[str, float]
    engine_lang: str = "en"
    scale: float = 1.0
    bgra: np.ndarray | None = field(default=None, repr=False)


_EDGE_SEPARATORS = "".join(SEPARATORS) + "-–—"  # hyphen, en and em dash


def _words_from(text: str, char_x: list[float], line: Line) -> list[Word]:
    """Words of a new reading of `line`. The line box stays exactly the same: with as many
    words as before, every word keeps its box; otherwise the boxes come from the position of
    the characters in the recognizer output."""
    tokens = text.split()
    if len(tokens) == len(line.words):
        return [Word(t, w.rect) for t, w in zip(tokens, line.words)]
    r = line.rect
    spans = [m.span() for m in re.finditer(r"\S+", text)]
    pitch = statistics.median(b - a for a, b in zip(char_x, char_x[1:])) if len(char_x) > 1 else r.h * 0.5
    words = []
    for n, (a, b) in enumerate(spans):
        x0 = r.x if n == 0 else max(r.x, char_x[a] - pitch / 2)
        x1 = r.right if n == len(spans) - 1 else min(r.right, char_x[b - 1] + pitch / 2)
        words.append(Word(text[a:b], Rect(x0, r.y, max(1.0, x1 - x0), r.h)))
    return words


def _tidy(text: str, xs: list[float], inline: bool) -> tuple[str, list[float]]:
    """Text with single spaces and no outer spaces, keeping one x per character. A part of a
    line cut at a separator also loses separators at its ends (its padded crop may catch one)."""
    pairs = list(zip(text, xs))
    edge = set(_EDGE_SEPARATORS + " ") if inline else {" "}
    while pairs and pairs[0][0] in edge:
        pairs.pop(0)
    while pairs and pairs[-1][0] in edge:
        pairs.pop()
    out = [p for i, p in enumerate(pairs) if not (p[0] == " " and pairs[i - 1][0] == " ")]
    return "".join(c for c, _ in out), [x for _, x in out]


def reread_block(block: Block, bgra: np.ndarray, rec, stop=None) -> bool:
    """Read the lines of a block again with the line recognizer and keep its confidence.
    `stop()` is checked between lines: when it says so, the block is left half read (the
    lines read so far are kept) and False is returned; a later call goes on from there."""
    if rec is None:
        block.meta["confidence"] = 1.0
        return True
    confs, weights = block.meta.setdefault("_read", ([], []))
    for line in block.lines[len(confs):]:
        if confs and stop is not None and stop():
            return False
        reading = rec.read(bgra, [line.rect])[0]
        text, xs = _tidy(reading.text, reading.char_x, line.inline)
        confs.append(reading.confidence)
        weights.append(max(1, len(text)))
        if text:
            line.words = _words_from(text, xs, line)
    del block.meta["_read"]
    block.meta["confidence"] = sum(c * w for c, w in zip(confs, weights)) / sum(weights) if weights else 0.0
    return True


def low_confidence(block: Block) -> bool:
    return block.meta.get("confidence", 1.0) < LOW_CONFIDENCE


LONG_WORDS = 6  # blocks with at least this many words decide which languages a screen has
MIXED_SHARE = 0.15  # a language with this share of the long text makes the screen multilingual


def detect_languages(blocks: list[Block], fallback: str) -> None:
    """Language of every block. On a screen in one language, short labels keep the screen
    language unless another one is clearly more likely. On a multilingual screen (a letter in
    German, French and Italian) every block is judged on its own, among the languages of the
    screen (any language of a long block), so "Cordiali saluti" stays Italian next to a French
    paragraph and "Fictitious sample document" English next to a German one."""
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
                cand = {l: p for l, p in probs.items() if l in present}
                b.lang = max(cand, key=cand.get) if cand else (screen_lang or fallback)
        else:
            b.lang = detect(b.text, prior=screen_lang)[0] or screen_lang or fallback


def _add_missed(found1x: list[Line], found2x: list[Line]) -> list[Line]:
    """The 1x lines plus what only the 2x reading found: whole lines, and words next to a 1x
    line (which then grows to include them, so the recognizer reads them too)."""
    lines = [Line(list(l.words), inline=l.inline) for l in found1x]
    words1x = [w.rect for l in found1x for w in l.words]
    for l2 in found2x:
        hits = [l for l in lines if l.rect.intersection_area(l2.rect) > 0]
        if not hits:
            lines.append(l2)
            continue
        extra = [w for w in l2.words if not any(w.rect.intersection_area(r) > 0 for r in words1x)]
        if extra:
            host = max(hits, key=lambda l: l.rect.intersection_area(l2.rect))
            host.words = sorted([*host.words, *extra], key=lambda w: w.rect.x)
    return lines


def first_pass(ocr: OcrBackend, bgra: np.ndarray, hint_lang: str) -> ScreenText:
    """Windows OCR of the whole screen, grouping and language detection. Fast (~100-250 ms)."""
    timings: dict[str, float] = {}
    available = ocr.available_languages()
    if not available:
        raise RuntimeError("no OCR language installed")
    lang = hint_lang if hint_lang in available else ("en" if "en" in available else available[0])

    t0 = time.perf_counter()
    lines = ocr.recognize(bgra, lang)
    scale = 1.0
    if lines and max(bgra.shape[:2]) * 2 <= 10000:
        if statistics.median(l.height for l in lines) < SMALL_TEXT_PX:
            # Tiny text: Windows OCR finds more lines at 2x.
            scale = 2.0
            lines = ocr.recognize(bgra, lang, scale=2.0)
        elif FIND_SMALL_PX and any(l.height < FIND_SMALL_PX for l in lines):
            lines = _add_missed(lines, ocr.recognize(bgra, lang, scale=2.0))
    lines = mark_separators(lines, bgra)
    timings["ocr"] = time.perf_counter() - t0

    t1 = time.perf_counter()
    blocks = group_lines(lines)
    timings["layout"] = time.perf_counter() - t1

    detect_languages(blocks, lang)
    log.info("OCR %s x%.0f: %d lines, %d blocks | ocr %.0f ms, layout %.0f ms",
             lang, scale, len(lines), len(blocks), timings["ocr"] * 1000, timings["layout"] * 1000)
    return ScreenText(blocks, screen_language(blocks), timings, lang, scale, bgra)


def screen_language(blocks: list[Block]) -> str | None:
    weights = Counter()
    for b in blocks:
        weights[b.lang] += len(b.text)
    return weights.most_common(1)[0][0] if weights else None


def read_screen(ocr: OcrBackend, bgra: np.ndarray, hint_lang: str) -> ScreenText:
    """Both readings of every block, synchronously (tools, tests and benchmarks)."""
    from .recognizer import recognizer

    st = first_pass(ocr, bgra, hint_lang)
    t0 = time.perf_counter()
    rec = recognizer()
    for b in st.blocks:
        reread_block(b, bgra, rec)
    st.timings["reread"] = time.perf_counter() - t0
    detect_languages(st.blocks, st.engine_lang)
    st.screen_lang = screen_language(st.blocks)
    return st
