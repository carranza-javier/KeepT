"""Second reading of the lines with the line recognizer (keept.ocr.recognizer)."""
import numpy as np
import pytest

from keept.ocr.layout import Block, Line, Rect, Word
from keept.ocr.pipeline import LOW_CONFIDENCE, _tidy, _words_from, low_confidence, reread_block
from keept.ocr.recognizer import Reading


def line(*specs, inline=False):
    return Line([Word(t, Rect(x, 10, w, 14)) for t, x, w in specs], inline=inline)


def test_same_word_count_keeps_the_boxes():
    l = line(("Ab", 0, 20), ("dem", 25, 30), ("1_", 60, 10), ("Dezember", 75, 70))
    new = _words_from("Ab dem 1. Dezember", [], l)
    assert [w.text for w in new] == ["Ab", "dem", "1.", "Dezember"]
    assert [w.rect for w in new] == [w.rect for w in l.words]


def test_other_word_count_takes_boxes_from_the_characters_and_keeps_the_line_box():
    l = line(("Musterwil,25", 0, 100), ("November", 105, 70))
    text = "Musterwil, 25 November"
    xs = [i * 8.0 + 4 for i in range(len(text))]
    new = _words_from(text, xs, l)
    assert [w.text for w in new] == ["Musterwil,", "25", "November"]
    assert Line(new).rect == l.rect
    assert new[0].rect.right <= new[1].rect.x <= new[1].rect.right <= new[2].rect.x


def test_tidy_keeps_one_position_per_character():
    text, xs = _tidy("  Grüsse   -", [float(i) for i in range(12)], inline=True)
    assert text == "Grüsse" and xs == [2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    text, xs = _tidy("a  b", [0.0, 1.0, 2.0, 3.0], inline=False)
    assert text == "a b" and xs == [0.0, 1.0, 3.0]


class FakeRecognizer:
    def __init__(self, readings):
        self.readings = list(readings)
        self.calls = 0

    def read(self, bgra, rects, heights=None):
        out = [Reading(t, c, [float(i) for i in range(len(t))]) for t, c in self.readings[:len(rects)]]
        del self.readings[:len(rects)]
        self.calls += 1
        return out


def test_reread_replaces_the_text_and_keeps_the_lines():
    lines = [line(("lunedi_", 0, 60), ("Si", 65, 15)), line(("puö", 0, 30))]
    block = Block(lines)
    reread_block(block, np.zeros((40, 200, 4), np.uint8), FakeRecognizer([("lunedì. Si", 0.99), ("può", 0.97)]))
    assert block.text == "lunedì. Si può"
    assert block.lines[0] is lines[0]  # the overlay tracks lines by identity
    assert not low_confidence(block)


@pytest.mark.parametrize("readings, low", [([("x0@", 0.4)], True), ([("", 0.0)], True), ([("Hallo", 0.95)], False)])
def test_low_confidence_blocks(readings, low):
    block = Block([line(("O@", 0, 20))])
    reread_block(block, np.zeros((40, 200, 4), np.uint8), FakeRecognizer(readings))
    assert low_confidence(block) == low
    assert LOW_CONFIDENCE > 0.5


def test_without_recognizer_the_windows_reading_stays():
    block = Block([line(("Hallo", 0, 40))])
    reread_block(block, np.zeros((40, 200, 4), np.uint8), None)
    assert block.text == "Hallo" and not low_confidence(block)


def test_real_recognizer_reads_what_windows_ocr_misreads():
    pytest.importorskip("onnxruntime")
    from test_letter import load, ocr_or_skip

    from keept.ocr.recognizer import recognizer

    bgra = load("letter_100.png")
    line = next(l for l in ocr_or_skip().recognize(bgra, "it") if l.text.startswith("Dal "))
    r = recognizer().read(bgra, [line.rect])[0]
    # Windows OCR: "Dal 10 dicembre ... il martedi invece del lunedi_ Si prega"
    assert r.text == "Dal 1° dicembre 2026 i rifiuti domestici saranno raccolti il martedì invece del lunedì. Si prega"
    assert r.confidence > 0.9


def test_reread_stops_between_lines_and_goes_on_later():
    lines = [line(("lunedi_", 0, 60), ("Si", 65, 15)), line(("puö", 0, 30))]
    block = Block(lines)
    rec = FakeRecognizer([("lunedì. Si", 0.99), ("può", 0.97)])
    bgra = np.zeros((40, 200, 4), np.uint8)
    assert reread_block(block, bgra, rec, stop=lambda: True) is False
    assert rec.calls == 1 and "confidence" not in block.meta
    assert reread_block(block, bgra, rec, stop=lambda: True) is False  # yields before reading more
    assert rec.calls == 1
    assert reread_block(block, bgra, rec) is True
    assert block.text == "lunedì. Si può"
    assert block.meta["confidence"] > 0.9


def test_lines_with_digits_are_read_at_full_height():
    from keept.ocr.pipeline import line_height
    from keept.ocr.recognizer import HEIGHT, TEXT_HEIGHT

    assert line_height(line(("Zuletzt", 0, 60), ("26.11.2026,", 65, 80))) == HEIGHT
    assert line_height(line(("Freundliche", 0, 60), ("Grüsse", 65, 50))) == TEXT_HEIGHT


def test_the_same_line_image_is_read_once():
    from keept.ocr import recognizer as R
    from keept.ocr.layout import Rect

    class Counting(R.LineRecognizer):
        def __init__(self):
            self.runs = 0

        def _run(self, crops, height=R.HEIGHT):
            self.runs += 1
            return [R.Reading("Hallo", 0.9, [1.0, 2.0, 3.0, 4.0, 5.0]) for _ in crops]

    R.clear_cache()
    rec = Counting()
    img = np.zeros((40, 200, 4), np.uint8)
    img[12:20, 20:60] = 255
    first = rec.read(img, [Rect(18, 10, 50, 12)])[0]
    moved = np.zeros((40, 300, 4), np.uint8)
    moved[12:20, 120:160] = 255  # same pixels further right
    again = rec.read(moved, [Rect(118, 10, 50, 12)])[0]
    assert rec.runs == 1 and again.text == "Hallo"
    assert again.char_x[0] - first.char_x[0] == 100  # positions follow the line
    rec.read(img, [Rect(18, 10, 50, 12)], [R.TEXT_HEIGHT])
    assert rec.runs == 2  # another input height is another reading
    R.clear_cache()
