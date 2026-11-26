from conftest import make_line

from keept.ocr.layout import Line, Rect, Word, group_lines, join_lines, split_line_on_gaps


def texts(blocks):
    return [b.text for b in blocks]


def test_paragraph_lines_form_one_block():
    lines = [
        make_line("Wir verwenden Cookies um Inhalte", 100, 100),
        make_line("zu personalisieren und die Zugriffe", 100, 126),
        make_line("zu analysieren.", 100, 152),
    ]
    blocks = group_lines(lines)
    assert len(blocks) == 1
    assert blocks[0].text.startswith("Wir verwenden") and blocks[0].text.endswith("analysieren.")


def test_title_and_body_are_separate_blocks():
    lines = [
        make_line("Settings", 100, 60, h=34, char_w=16),
        make_line("Change how the app looks", 100, 104),
        make_line("and behaves on this device", 100, 130),
    ]
    assert texts(group_lines(lines)) == ["Settings", "Change how the app looks and behaves on this device"]


def test_far_apart_lines_are_separate():
    lines = [make_line("First paragraph", 100, 100), make_line("Second paragraph", 100, 200)]
    assert len(group_lines(lines)) == 2


def test_columns_are_separate_blocks():
    lines = [
        make_line("Left column text", 100, 100),
        make_line("Right column text", 900, 100),
        make_line("continues here", 100, 126),
        make_line("continues there", 900, 126),
    ]
    blocks = group_lines(lines)
    assert sorted(texts(blocks)) == ["Left column text continues here", "Right column text continues there"]


def test_centered_lines_join():
    lines = [make_line("A centered title", 400, 100), make_line("subtitle", 440, 126)]
    assert len(group_lines(lines)) == 1


def test_line_split_on_large_gap():
    line = Line([Word("Name", Rect(10, 0, 40, 20)), Word("Value", Rect(300, 0, 50, 20))])
    assert [l.text for l in split_line_on_gaps(line)] == ["Name", "Value"]


def test_normal_spacing_not_split():
    line = make_line("one two three", 0, 0)
    assert len(split_line_on_gaps(line)) == 1


def test_buttons_in_a_row_are_separate():
    lines = [Line([Word("Accept", Rect(100, 400, 60, 20)), Word("Reject", Rect(260, 400, 60, 20))])]
    assert texts(group_lines(lines)) == ["Accept", "Reject"]


def test_dehyphenation():
    assert join_lines(["Die Ein-", "stellungen sind neu"]) == "Die Einstellungen sind neu"
    assert join_lines(["Hello", "world"]) == "Hello world"
    assert join_lines(["Pre-", "Release"]) == "Pre- Release"


def test_block_ids_follow_reading_order():
    lines = [make_line("bottom", 100, 500), make_line("top", 100, 100)]
    blocks = group_lines(lines)
    assert [b.id for b in blocks] == [0, 1]
    assert blocks[0].text == "top"


def test_cover_rect_contains_text_rect():
    b = group_lines([make_line("hello world", 100, 100)])[0]
    c, r = b.cover_rect(), b.rect
    assert c.x < r.x and c.y < r.y and c.right > r.right and c.bottom > r.bottom


def test_caps_label_is_not_part_of_the_next_paragraph():
    # "FRANÇAIS" with a cedilla is as tall as the body text, but it is a label.
    lines = [
        make_line("FRANCAIS", 100, 100, h=15),
        make_line("A partir du 1er décembre 2026, les ordures", 100, 120, h=15),
        make_line("ménagères seront collectées le mardi.", 100, 138, h=15),
    ]
    assert texts(group_lines(lines)) == ["FRANCAIS", "A partir du 1er décembre 2026, les ordures ménagères seront collectées le mardi."]


def test_wrapped_caps_lines_stay_together():
    lines = [make_line("IMPORTANT NOTICE FOR ALL", 100, 100), make_line("RESIDENTS OF THE TOWN", 100, 126)]
    assert len(group_lines(lines)) == 1


def test_separators_split_items_that_never_join_lines_below():
    lines = [
        make_line("Freundliche Grüsse • Meilleures salutations • Cordiali saluti", 100, 100),
        make_line("Gemeindeverwaltung Musterwil", 100, 124),
    ]
    assert texts(group_lines(lines)) == ["Freundliche Grüsse", "Meilleures salutations", "Cordiali saluti",
                                        "Gemeindeverwaltung Musterwil"]


def test_leading_bullet_is_a_list_marker():
    lines = [make_line("• First item of the list that", 100, 100), make_line("wraps to a second line", 100, 126)]
    assert texts(group_lines(lines)) == ["First item of the list that wraps to a second line"]


def test_paragraph_break_after_a_sentence():
    lines = [
        make_line("Si prega di depositare i sacchi entro le ore 7.00.", 100, 100, h=15),
        make_line("In caso di forti nevicate la raccolta slitta.", 100, 118, h=15),
        make_line("Questions? The office is open Monday to Friday.", 100, 145, h=15),
    ]
    assert len(group_lines(lines)) == 2
