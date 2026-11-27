"""Separators the OCR did not read."""
import numpy as np

from keept.ocr.cleanup import mark_separators
from keept.ocr.layout import Line, Rect, Word, group_lines


def words(lines):
    return [w.text for l in lines for w in l.words]


def canvas(w=300, h=40):
    return np.full((h, w, 4), 255, np.uint8)


def ink(img, x0, y0, x1, y1):
    img[y0:y1, x0:x1, :3] = 0


def line_of_boxes(img, specs, y=10, h=14):
    """Words drawn as ink boxes; returns OCR words for them."""
    out = []
    for text, x, w in specs:
        ink(img, x, y + 2, x + w, y + h - 2)
        out.append(Word(text, Rect(x, y, w, h)))
    return out


def test_lost_separator_dot_splits_the_line_but_a_lost_word_does_not():
    img = canvas(700)
    # "Freundliche Grüsse · Meilleures salutations": the OCR returned the words but not the dot.
    first = line_of_boxes(img, [("Freundliche", 10, 80), ("Grüsse", 95, 45), ("Meilleures", 160, 70),
                                ("salutations", 235, 80)])
    ink(img, 149, 16, 151, 18)  # the small dot, in the middle of the gap 140..160
    # "au plus tard à 7 h.": the OCR dropped "à", a glyph as tall as the x-height.
    second = line_of_boxes(img, [("au", 400, 16), ("plus", 421, 28), ("tard", 454, 28), ("7", 502, 8),
                                 ("h.", 515, 12)])
    ink(img, 488, 14, 496, 22)
    lines = mark_separators([Line(first), Line(second)], img)
    assert "•" in words([lines[0]]) and "•" not in words([lines[1]])
    blocks = group_lines(lines)
    assert sorted(b.text for b in blocks) == ["Freundliche Grüsse", "Meilleures salutations", "au plus tard 7 h."]


def test_middle_dot_read_as_hyphen_is_a_separator_but_a_hyphen_is_not():
    img = canvas(700)
    first = line_of_boxes(img, [("hiver", 10, 40), ("Raccolta", 66, 60)])
    first.insert(1, Word("-", Rect(56, 10, 3, 14)))
    ink(img, 56, 16, 58, 18)  # a 2x2 dot
    second = line_of_boxes(img, [("Montag", 300, 50), ("Freitag", 368, 50)])
    second.insert(1, Word("-", Rect(356, 10, 6, 14)))
    ink(img, 356, 17, 362, 18)  # a 6x1 dash
    lines = mark_separators([Line(first), Line(second)], img)
    assert words(lines) == ["hiver", "•", "Raccolta", "Montag", "-", "Freitag"]
