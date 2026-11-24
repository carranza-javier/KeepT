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
