"""OCR fixes: periods read as "_", raised ordinal signs read as "0", lost separators."""
import numpy as np
import pytest

from conftest import make_line

from keept.ocr.cleanup import clean, fix_first, fix_periods, mark_separators, merge_readings, raised_last_glyph
from keept.ocr.layout import Line, Rect, Word, group_lines


def words(lines):
    return [w.text for l in lines for w in l.words]


def test_lone_underscore_after_a_word_is_a_period():
    line = Line([Word("Ab", Rect(0, 0, 20, 14)), Word("dem", Rect(25, 0, 30, 14)), Word("1", Rect(60, 0, 8, 14)),
                 Word("_", Rect(69, 10, 4, 3)), Word("Dezember", Rect(78, 0, 70, 14))])
    assert words(fix_periods([line])) == ["Ab", "dem", "1.", "Dezember"]


def test_underscores_in_words():
    assert words(fix_periods([make_line("del lunedi_ Si entro le ore 7_00_ In 11_30", 0, 0)])) == \
        ["del", "lunedi.", "Si", "entro", "le", "ore", "7.00.", "In", "11.30"]


def test_identifiers_keep_their_underscores():
    text = "snake_case __init__ my_var_ file_name.txt _private"
    assert words(fix_periods([make_line(text, 0, 0)])) == text.split()


def test_first_of_the_month_in_french():
    assert words(fix_first([make_line("du ler décembre et Ier mai", 0, 0)])) == \
        ["du", "1er", "décembre", "et", "1er", "mai"]


def test_merge_keeps_accents_of_1x_and_punctuation_of_2x():
    two_x = [Line([Word("Säcke", Rect(0, 0, 40, 14)), Word("spatestens.", Rect(45, 0, 80, 14))])]
    one_x = [Line([Word("Sacke", Rect(0, 0, 40, 14)), Word("spätestens_", Rect(45, 0, 80, 14))]),
             Line([Word("Only1x", Rect(0, 100, 50, 14))])]
    merged = merge_readings(two_x, one_x)
    assert words(merged) == ["Säcke", "spätestens.", "Only1x"]


def test_merge_keeps_words_only_the_1x_reading_found():
    two_x = [Line([Word("partir", Rect(20, 0, 40, 14)), Word("du", Rect(65, 0, 15, 14))])]
    one_x = [Line([Word("À", Rect(0, 0, 10, 14)), Word("partir", Rect(20, 0, 40, 14)), Word("du", Rect(65, 0, 15, 14))])]
    assert words(merge_readings(two_x, one_x)) == ["À", "partir", "du"]


def canvas(w=300, h=40):
    return np.full((h, w, 4), 255, np.uint8)


def ink(img, x0, y0, x1, y1):
    img[y0:y1, x0:x1, :3] = 0


def ordinal_image(raised: bool):
    """A "1" (tall bar) and a second glyph: a small ring up high (°) or a full height "0"."""
    img = canvas()
    ink(img, 12, 10, 14, 26)  # "1": cap height 10..26, baseline at 26
    if raised:
        ink(img, 17, 10, 22, 11); ink(img, 17, 14, 22, 15); ink(img, 17, 10, 18, 15); ink(img, 21, 10, 22, 15)
    else:
        ink(img, 17, 10, 25, 11); ink(img, 17, 25, 25, 26); ink(img, 17, 10, 18, 26); ink(img, 24, 10, 25, 26)
    return img, Rect(11, 9, 16, 18)


@pytest.mark.parametrize("raised", [True, False])
def test_raised_ordinal_sign(raised):
    img, rect = ordinal_image(raised)
    assert raised_last_glyph(img, rect) == raised


def test_ten_read_from_first_with_degree_sign_is_fixed():
    img, rect = ordinal_image(True)
    assert words(clean([Line([Word("10", rect)])], img)) == ["1°"]
    img, rect = ordinal_image(False)
    assert words(clean([Line([Word("10", rect)])], img)) == ["10"]


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
