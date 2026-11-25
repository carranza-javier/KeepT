import math

from conftest import make_line

from keept.ocr.layout import group_lines
from keept.overlay.selection import classify, point_in_polygon, select_blocks


def screen_blocks():
    lines = [
        make_line("Title text here", 100, 50, h=30, char_w=15),
        make_line("First line of the paragraph", 100, 120),
        make_line("second line of the paragraph", 100, 146),
        make_line("third line of the paragraph", 100, 172),
        make_line("Button", 800, 400),
    ]
    return group_lines(lines)


def circle(cx, cy, r, n=40):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]


def test_classify_click():
    g = classify([(10, 10), (12, 11), (11, 13)])
    assert g.kind == "click" and g.points == ((10, 10),)


def test_classify_straight_diagonal_is_rect():
    pts = [(100 + i * 10, 100 + i * 5 + (1 if i % 2 else 0)) for i in range(30)]
    g = classify(pts)
    assert g.kind == "rect"
    assert (g.rect.x, g.rect.y) == (100, 100)
    assert g.rect.w == 290


def test_classify_curve_is_lasso():
    assert classify(circle(300, 300, 100)).kind == "lasso"


def test_horizontal_line_is_not_rect():
    assert classify([(100 + i * 10, 200) for i in range(30)]).kind == "lasso"


def test_point_in_polygon():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon(5, 5, square)
    assert not point_in_polygon(15, 5, square)


def test_click_selects_block_under_pointer():
    blocks = screen_blocks()
    sel = select_blocks(blocks, classify([(150, 150)]))
    assert len(sel) == 1 and sel[0].text.startswith("First line")


def test_click_on_empty_space_selects_nothing():
    assert select_blocks(screen_blocks(), classify([(600, 700)])) == []


def test_rect_selects_whole_paragraph():
    blocks = screen_blocks()
    g = classify([(90 + i * 20, 110 + i * 4) for i in range(21)])  # (90,110) -> (490,190)
    assert g.kind == "rect"
    sel = select_blocks(blocks, g)
    assert [len(b.lines) for b in sel] == [3]


def test_lasso_selects_only_circled_lines():
    blocks = screen_blocks()
    lasso = [(80, 112), (420, 112), (420, 160), (80, 160), (80, 113)]
    sel = select_blocks(blocks, classify(lasso))
    assert len(sel) == 1
    assert sel[0].text == "First line of the paragraph second line of the paragraph"
    assert sel[0].meta["parent"] == blocks[1].id


def test_lasso_around_everything():
    blocks = screen_blocks()
    sel = select_blocks(blocks, classify(circle(500, 250, 700)))
    assert len(sel) == len(blocks)


def test_underline_stroke_selects_touched_line():
    blocks = screen_blocks()
    stroke = [(100 + i * 10, 415) for i in range(0, 80)]
    sel = select_blocks(blocks, classify(stroke))
    assert [b.text for b in sel] == ["Button"]


def test_file_names_urls_and_mail_are_not_translated():
    from keept.overlay.overlay_window import looks_untranslatable

    for text in ("requirements.txt", "KeepT.pyw", "Bericht_2026-11.pdf", "https://example.org/a",
                 "www.sbb.ch", "info@example.ch"):
        assert looks_untranslatable(text), text
    for text in ("Dateiordner", "Release notes", "Version 2.5 ist da.", "Datei.  Weiter"):
        assert not looks_untranslatable(text), text


def test_unsure_language_without_model_does_not_trigger_a_download():
    from types import SimpleNamespace

    from conftest import make_line

    from keept.ocr.layout import Block
    from keept.overlay.overlay_window import OverlayWindow

    installed = {("de", "es"), ("en", "es")}
    store = SimpleNamespace(get=lambda s, t: object() if (s, t) in installed else None)
    fake = SimpleNamespace(engine=SimpleNamespace(translator=SimpleNamespace(store=store)), screen_lang="de")

    def lang_for(text, detected):
        block = Block([make_line(text, 0, 0)], lang=detected)
        return OverlayWindow._usable_language(fake, block, "es")

    # Truncated Explorer text guessed as Italian with low confidence: no it->es download.
    assert lang_for("Python File (no cons...", "it") in ("de", "en", "es")
    # A clear, long Italian sentence still asks for the Italian model.
    assert lang_for("Impossibile salvare il file perché il disco è pieno, riprova più tardi per favore.", "it") == "it"
    # Installed languages are kept as detected.
    assert lang_for("Die Datei konnte nicht gespeichert werden.", "de") == "de"
