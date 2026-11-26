import numpy as np

from keept.ocr.layout import Rect
from keept.overlay.render import (
    contrast_text,
    fit_text,
    is_boxed,
    sample_background,
    sample_text_color,
    wrap,
)


def canvas(w, h, rgb):
    img = np.zeros((h, w, 4), np.uint8)
    img[..., 0], img[..., 1], img[..., 2], img[..., 3] = rgb[2], rgb[1], rgb[0], 255
    return img


def paint(img, x0, y0, x1, y1, rgb):
    img[y0:y1, x0:x1, 0], img[y0:y1, x0:x1, 1], img[y0:y1, x0:x1, 2] = rgb[2], rgb[1], rgb[0]


def test_background_is_median_of_border():
    img = canvas(200, 100, (240, 240, 240))
    paint(img, 50, 40, 150, 60, (20, 20, 20))  # "text" inside the rect
    paint(img, 0, 0, 3, 100, (255, 0, 0))  # far away noise
    assert sample_background(img, Rect(50, 40, 100, 20)) == (240, 240, 240)


def test_background_ignores_small_intrusions():
    img = canvas(200, 100, (30, 40, 50))
    paint(img, 45, 35, 60, 38, (250, 250, 250))  # a bit of another element touching the ring
    assert sample_background(img, Rect(50, 40, 100, 20)) == (30, 40, 50)


def test_background_at_screen_edge():
    img = canvas(100, 50, (10, 200, 10))
    assert sample_background(img, Rect(0, 0, 40, 20)) == (10, 200, 10)


def test_text_color_keeps_coloured_text():
    img = canvas(200, 100, (255, 255, 255))
    for x in range(52, 148, 6):  # stripes of blue "glyphs"
        paint(img, x, 42, x + 2, 58, (11, 87, 208))
    assert sample_text_color(img, Rect(50, 40, 100, 20), (255, 255, 255)) == (11, 87, 208)


def test_text_color_falls_back_on_low_contrast():
    img = canvas(200, 100, (200, 200, 200))
    paint(img, 60, 45, 140, 55, (180, 180, 180))
    color = sample_text_color(img, Rect(50, 40, 100, 20), (200, 200, 200))
    assert color == contrast_text((200, 200, 200))


def test_contrast_text():
    assert contrast_text((255, 255, 255))[0] < 60
    assert contrast_text((20, 20, 30))[0] > 200
    assert contrast_text((11, 87, 208))[0] > 200


def test_is_boxed_detects_buttons():
    img = canvas(300, 200, (255, 255, 255))
    paint(img, 80, 80, 220, 120, (11, 87, 208))  # button
    assert is_boxed(img, Rect(110, 92, 80, 16), (11, 87, 208), 16)
    assert not is_boxed(img, Rect(110, 20, 80, 16), (255, 255, 255), 16)


def mono(text, px):
    return len(text) * px * 0.5


def test_wrap_respects_width():
    lines = wrap("one two three four five six", 60, 10, mono)
    assert all(mono(l, 10) <= 60 for l in lines)
    assert " ".join(lines) == "one two three four five six"


def test_wrap_breaks_long_word():
    lines = wrap("Datenschutzeinstellungen", 50, 10, mono)
    assert all(mono(l, 10) <= 50 for l in lines) and "".join(lines) == "Datenschutzeinstellungen"


def test_fit_keeps_size_when_it_fits():
    r = fit_text("short", 200, 30, 20, 10, mono)
    assert r.px == 20 and r.lines == ["short"] and r.box_height == 30


def test_fit_shrinks_longer_translation():
    text = "a considerably longer translated sentence"
    r = fit_text(text, 200, 36, 20, 10, mono)
    # shrinks a little, then grows the background rather than becoming tiny
    assert 20 * 0.9 <= r.px < 20 and r.box_height >= r.height > 36
    assert all(mono(l, r.px) <= 200 for l in r.lines)


def test_fit_without_room_below_keeps_shrinking():
    text = "a considerably longer translated sentence"
    r = fit_text(text, 200, 36, 20, 10, mono, max_grow=1.0)
    assert r.px < 20 * 0.9 and r.height <= 36 * 1.02 and r.box_height == 36


def test_fit_grows_background_before_illegible():
    text = "word " * 60
    r = fit_text(text, 100, 20, 16, 10, mono)
    assert r.px >= 10
    assert r.box_height > 20
    assert r.box_height >= r.height


def test_fit_never_below_minimum():
    r = fit_text("x " * 500, 50, 10, 30, 12, mono)
    assert r.px == 12


def test_free_space_right_stops_at_content():
    from keept.overlay.render import free_space_right

    img = canvas(400, 60, (255, 255, 255))
    paint(img, 250, 20, 260, 40, (0, 0, 0))  # another word further right
    assert free_space_right(img, Rect(50, 20, 60, 20), (255, 255, 255), 300) == 139
    img2 = canvas(400, 60, (255, 255, 255))
    paint(img2, 200, 0, 400, 60, (30, 30, 30))  # panel edge
    assert 88 <= free_space_right(img2, Rect(50, 20, 60, 20), (255, 255, 255), 300) <= 90


def test_title_under_panel_edge_is_not_boxed():
    img = canvas(300, 200, (200, 210, 225))  # page background
    paint(img, 0, 60, 300, 200, (253, 246, 227))  # panel starting just above the title
    assert not is_boxed(img, Rect(40, 80, 120, 20), (253, 246, 227), 20)


def test_highlighted_table_row_is_not_boxed():
    img = canvas(800, 200, (30, 30, 30))
    paint(img, 0, 80, 800, 120, (70, 70, 70))  # full width selected row
    assert not is_boxed(img, Rect(300, 92, 80, 16), (70, 70, 70), 16)


def test_button_shape_bounds_radius_and_room():
    from keept.overlay.render import button_shape

    img = canvas(600, 200, (255, 255, 255))
    # rounded button 200x50 at (200, 75), radius 25, on a white page; a wall at x=500
    import math as _m

    for y in range(75, 125):
        for x in range(200, 400):
            if x < 225 or x > 374:
                cx = 225 if x < 225 else 374
                if _m.hypot(x - cx, y - 100) > 25:
                    continue
            img[y, x, :3] = (208, 87, 11)  # BGR of (11, 87, 208)
    paint(img, 500, 0, 600, 200, (30, 30, 30))
    shape = button_shape(img, Rect(250, 92, 100, 16), (11, 87, 208), 16)
    assert shape is not None
    assert abs(shape.rect.x - 200) <= 1 and abs(shape.rect.right - 400) <= 1
    assert abs(shape.rect.y - 75) <= 1 and abs(shape.rect.bottom - 125) <= 1
    assert 18 <= shape.radius <= 25
    assert 190 <= shape.room_left <= 200 and 95 <= shape.room_right <= 100


def test_large_panel_is_not_a_button():
    from keept.overlay.render import button_shape

    img = canvas(800, 600, (11, 87, 208))
    assert button_shape(img, Rect(300, 290, 100, 16), (11, 87, 208), 16) is None


def test_weight_classes_prefer_regular():
    from keept.overlay.render import weight_class

    # measured stroke ratios: Arial body text on screen 0.10-0.125, Segoe UI semibold 0.13-0.15,
    # bold 0.15-0.23
    assert [weight_class(r) for r in (0.099, 0.113, 0.118, 0.124)] == [0, 0, 0, 0]
    assert [weight_class(r) for r in (0.138, 0.152)] == [1, 1]
    assert [weight_class(r) for r in (0.174, 0.19)] == [2, 2]
