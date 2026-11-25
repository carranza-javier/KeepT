"""Full screen overlay: frozen capture, edge glow, selection and translated blocks.

State machine: idle -> ready (OCR running or done) -> translating -> showing -> idle.

Geometry: OCR blocks live in physical pixels of the capture. The window works
in Qt logical pixels; `self.scale` (physical per logical) converts between
them, which keeps coordinates exact at 100 %, 125 %, 150 % and on any monitor.
"""

from __future__ import annotations

import logging
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum

from PySide6.QtCore import QElapsedTimer, QEvent, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetricsF, QGuiApplication, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from .. import i18n
from ..capture import Capture
from ..engine import Engine, TranslationJob
from ..ocr.layout import Block, Rect
from ..ocr.pipeline import ScreenText
from ..platform import services
from . import effects
from .pill import SHADOW, LangMenu, Pill, ui_font
from .render import FitResult, button_shape, fit_text, free_space_below, free_space_left, free_space_right, is_boxed, sample_background, sample_text_color, stroke_ratio, weight_class
from .selection import Gesture, block_at, classify, select_blocks

log = logging.getLogger(__name__)

GLOW_PX = 8.0  # logical
STROKE_PX = 4.0  # logical
MIN_TEXT_PX = 10.0  # logical, smallest legible translated text
FADE_MS = 220.0


_UNTRANSLATABLE = re.compile(
    r"[\w\-.~()\[\]]+\.[A-Za-z0-9]{1,5}"  # file names: report.pdf, requirements.txt
    r"|(?:https?://|www\.)\S+"  # URLs
    r"|[\w.+-]+@[\w-]+\.[\w.-]+"  # e-mail addresses
)


def looks_untranslatable(text: str) -> bool:
    """File names, URLs and e-mail addresses are left as they are."""
    return bool(_UNTRANSLATABLE.fullmatch(text.strip()))


class State(Enum):
    IDLE = "idle"
    READY = "ready"
    TRANSLATING = "translating"
    SHOWING = "showing"


@dataclass
class Item:
    key: int
    block: Block
    line_ids: frozenset
    bg: QColor
    fg: QColor
    boxed: bool
    weight: int = 0  # 0 regular, 1 semibold, 2 bold
    extra_w: float = 0.0  # free background to the right that a single line may use (phys px)
    status: str = "pending"  # pending | done | error
    text: str = ""
    fit: FitResult | None = None
    layout: tuple | None = None  # (font, [(x, baseline, text)], box) in logical px
    t_added: float = 0.0
    t_done: float = 0.0
    meta: dict = field(default_factory=dict)


class OverlayWindow(QWidget):
    closed = Signal()
    target_changed = Signal(str)
    ocr_pack_missing = Signal(str)  # language read without its Windows OCR pack

    _session_counter = 0  # global so that sessions of different overlay windows never collide

    def __init__(self, engine: Engine, target_lang: str, dark: bool, debug_blocks: bool = False, screen=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.NoDropShadowWindowHint)
        self.setWindowTitle("KeepT Overlay")
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        # Showing with activation makes Windows talk synchronously to the previous foreground
        # window, which can stall show() for hundreds of ms. Show first, activate right after.
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.engine = engine
        self.target = target_lang
        self.debug_blocks = debug_blocks
        self.hint_lang = "en"
        self.state = State.IDLE
        self.session = 0

        self.clock = QElapsedTimer()
        self.pill = Pill(dark, self)
        self.menu = LangMenu(self.pill.theme, self)
        self.pill.translate_all.connect(self.translate_all)
        self.pill.copy_all.connect(self.copy_all)
        self.pill.toggle_original.connect(self.toggle_original)
        self.pill.open_languages.connect(self._toggle_menu)
        self.menu.chosen.connect(self.set_target)

        self.glow = effects.EdgeGlow()
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)

        engine.ocr_finished.connect(self._on_ocr_finished)
        engine.ocr_failed.connect(self._on_ocr_failed)
        engine.ocr_refined.connect(self._on_ocr_refined)
        engine.translated.connect(self._on_translated)
        engine.translation_finished.connect(self._on_translation_finished)
        engine.translation_failed.connect(self._on_translation_failed)
        engine.progress.connect(self._on_progress)

        self._reset_session_state()
        self._fonts: dict[tuple[float, int], tuple[QFont, QFontMetricsF]] = {}
        # The window is shown once and then kept cloaked (invisible through DWM) and parked
        # off screen while idle. Opening is a move plus uncloak, which is consistently fast,
        # while show() can stall for hundreds of ms.
        plat = services()
        self._hwnd = int(self.winId())
        plat.prepare_overlay_window(self._hwnd)
        plat.set_cloaked(self._hwnd, True)
        self._prev_foreground = 0
        # One overlay per monitor: placing it on its screen once (cloaked) fixes its DPI, so
        # opening never has to go through a DPI change (which can cost ~300 ms).
        self.home_screen = screen or QGuiApplication.primaryScreen()
        self.setScreen(self.home_screen)
        self.setGeometry(self.home_screen.geometry())
        self.show()
        plat.park_window(self._hwnd)

    # ------------------------------------------------------------------ session
    def _reset_session_state(self) -> None:
        self.capture: Capture | None = None
        self.pixmap: QPixmap | None = None
        self.scale = 1.0
        self.blocks: list[Block] = []
        self.screen_lang: str | None = None
        self.ocr_done = False
        self.ocr_error: str | None = None
        self.pending_action: tuple | None = None
        self.items: dict[int, Item] = {}
        self.stroke: list[QPointF] = []  # logical points
        self.dragging = False
        self.stroke_fade_from = -1.0
        self.last_stroke_path: QPainterPath | None = None
        self.show_original = False
        self.space_held = False
        self.original_mix = 0.0  # 0 = translation visible, 1 = original visible
        self.dim = 0.0
        self.toasts: list[tuple[str, QPointF, float]] = []
        self._t_hotkey = 0.0
        self._first_paint_logged = False
        self._was_active = False

    def warm_up(self) -> None:
        """Paint one frame off screen so fonts, glyph caches and gradients are ready."""
        import numpy as np

        from ..platform import MonitorInfo

        bgra = np.zeros((64, 64, 4), np.uint8)
        self.capture = Capture(MonitorInfo("", 0, 0, 64, 64, 1.0), bgra)
        self.pixmap = QPixmap.fromImage(QImage(bgra.data, 64, 64, 256, QImage.Format_RGB32))
        self.clock.start()
        img = QImage(self.size(), QImage.Format_RGB32)
        self.render(img)
        for weight in (0, 1, 2):
            self._font(20, weight)
        self._reset_session_state()
        self._first_paint_logged = True
        self._fonts.clear()

    def is_open(self) -> bool:
        return self.state != State.IDLE

    def open(self, capture: Capture, t_hotkey: float) -> None:
        OverlayWindow._session_counter += 1
        self.session = OverlayWindow._session_counter
        self.engine.set_active(self.session)
        self._reset_session_state()
        self._t_hotkey = t_hotkey
        self.capture = capture
        tm = [time.perf_counter()]
        plat = services()
        self._prev_foreground = plat.foreground_window()
        screen = self._screen_for(capture.monitor)
        if screen is not None:
            if self.screen() is not screen:
                self.setScreen(screen)
            self.setGeometry(screen.geometry())
        else:
            dpr = capture.monitor.scale
            self.setGeometry(int(capture.monitor.left / dpr), int(capture.monitor.top / dpr),
                             int(capture.width / dpr), int(capture.height / dpr))
        # Exact device pixel ratio of the target screen (width ratios can be off by a fraction
        # when the resolution is not divisible by the scale, e.g. 1366 px at 125 %).
        self.scale = screen.devicePixelRatio() if screen is not None else capture.monitor.scale
        img = QImage(capture.bgra.data, capture.width, capture.height, capture.width * 4, QImage.Format_RGB32)
        self.pixmap = QPixmap.fromImage(img)
        self.pixmap.setDevicePixelRatio(self.scale)
        tm.append(time.perf_counter())
        self.state = State.READY
        self.glow.level = 1.0
        # Per zone palette for the glow: how light the screen is, from a 1/8 sample.
        sample = capture.bgra[::8, ::8, :3].astype("float32") / 255.0
        lightness = sample[..., 2] * 0.2126 + sample[..., 1] * 0.7152 + sample[..., 0] * 0.0722
        self.glow.set_background(lightness, self.size())
        self.pill.set_mode("ready")
        self.menu.hide()
        self.place_pill()
        self.clock.start()
        self.timer.start()
        tm.append(time.perf_counter())
        self.repaint()  # first frame is rendered while still cloaked: no stale frame shows up
        plat.set_cloaked(self._hwnd, False)
        tm.append(time.perf_counter())
        QTimer.singleShot(0, self._activate)
        tm.append(time.perf_counter())
        self.engine.start_ocr(self.session, capture.bgra, self.hint_lang)
        log.debug("open: geometry+pixmap %.0f ms, setup %.0f ms, paint+uncloak %.0f ms, rest %.0f ms",
                  *[(b - a) * 1000 for a, b in zip(tm, tm[1:])])
        log.info("Overlay on %s: %dx%d physical, scale %.2f (dpr %.2f)", capture.monitor.device, capture.width,
                 capture.height, self.scale, self.devicePixelRatioF())

    def _activate(self) -> None:
        if self.state == State.IDLE:
            return
        t0 = time.perf_counter()
        self.raise_()
        self.activateWindow()
        services().bring_to_front(int(self.winId()))
        self.setFocus(Qt.ActiveWindowFocusReason)
        log.debug("activation took %.0f ms", (time.perf_counter() - t0) * 1000)

    @staticmethod
    def _screen_for(monitor):
        """QScreen for a monitor in physical coordinates. Qt keeps each screen's native origin,
        so origin and physical size identify it (QScreen.name() is a friendly name on some
        monitors, not the device name)."""
        screens = QGuiApplication.screens()
        for s in screens:
            g, dpr = s.geometry(), s.devicePixelRatio()
            if (g.x(), g.y()) == (monitor.left, monitor.top) and abs(g.width() * dpr - monitor.width) <= 2:
                return s
        for s in screens:
            if s.name() == monitor.device:
                return s
        return None

    def close_overlay(self) -> None:
        if self.state == State.IDLE:
            return
        self.state = State.IDLE
        self.engine.set_active(0)
        self.timer.stop()
        plat = services()
        plat.set_cloaked(self._hwnd, True)
        plat.park_window(self._hwnd)
        plat.restore_foreground(self._prev_foreground)
        self.menu.hide()
        if self.screen_lang:
            self.hint_lang = self.screen_lang
        self._reset_session_state()
        self.closed.emit()

    def now(self) -> float:
        return float(self.clock.elapsed()) if self.clock.isValid() else 0.0

    # --------------------------------------------------------------- geometry
    def to_phys(self, p: QPointF) -> tuple[float, float]:
        return p.x() * self.scale, p.y() * self.scale

    def to_logical(self, r: Rect) -> QRectF:
        s = self.scale
        return QRectF(r.x / s, r.y / s, r.w / s, r.h / s)

    def place_pill(self) -> None:
        if not hasattr(self, "menu"):
            return  # still constructing
        self.pill.adjustSize()
        x = (self.width() - self.pill.width()) / 2
        y = self.height() - self.pill.height() - 36 + SHADOW
        t = self.now()
        if t < 420:
            y += (1 - effects.ease_out_cubic(max(0.0, t - 60) / 360)) * (self.pill.height() + 48)
        self.pill.move(int(x), int(y))
        if self.menu.isVisible():
            self._place_menu()

    def _place_menu(self) -> None:
        self.menu.adjustSize()
        btn = self.pill.btn_lang
        center = btn.mapTo(self, QPointF(btn.width() / 2, 0).toPoint())
        self.menu.move(int(center.x() - self.menu.width() / 2), self.pill.y() - self.menu.height() + SHADOW + 4)

    # ---------------------------------------------------------------- fonts
    _WEIGHTS = (QFont.Normal, QFont.DemiBold, QFont.Bold)

    def _font(self, px_phys: float, weight: int = 0) -> tuple[QFont, QFontMetricsF]:
        key = (round(px_phys * 4) / 4, weight)
        cached = self._fonts.get(key)
        if cached is None:
            f = QFont("Segoe UI")
            f.setPointSizeF(max(1.0, key[0] / self.scale * 0.75))
            f.setWeight(self._WEIGHTS[weight])
            f.setHintingPreference(QFont.PreferNoHinting)
            cached = (f, QFontMetricsF(f))
            self._fonts[key] = cached
        return cached

    def _measure(self, text: str, px_phys: float, weight: int = 0) -> float:
        return self._font(px_phys, weight)[1].horizontalAdvance(text) * self.scale

    # ------------------------------------------------------------- OCR events
    def _on_ocr_finished(self, session: int, result: ScreenText) -> None:
        if session != self.session or self.state == State.IDLE:
            return
        self.blocks = result.blocks
        self.screen_lang = result.screen_lang
        self.ocr_done = True
        log.info("OCR ready %.0f ms after hotkey (%d blocks)", (time.perf_counter() - self._t_hotkey) * 1000, len(self.blocks))
        if self.pending_action:
            action, self.pending_action = self.pending_action, None
            self.pill.end_message()
            action[0](*action[1:])

    def _on_ocr_refined(self, session: int, better: dict) -> None:
        """Better readings (right OCR language) for blocks nobody has asked to translate yet."""
        if session != self.session or self.state == State.IDLE:
            return
        used = set()
        for it in self.items.values():
            used |= it.line_ids
        n = 0
        for b in self.blocks:
            lines = better.get(b.id)
            if lines and not any(id(l) in used for l in b.lines):
                b.lines = lines
                n += 1
        log.info("OCR refined %d block(s) %.0f ms after hotkey", n, (time.perf_counter() - self._t_hotkey) * 1000)

    def _on_ocr_failed(self, session: int, kind: str) -> None:
        if session != self.session or self.state == State.IDLE:
            return
        self.ocr_done = True
        self.ocr_error = kind
        if self.pending_action:
            self.pending_action = None
            self._show_ocr_error()

    def _show_ocr_error(self) -> None:
        self.pill.show_message(i18n.tr("err_no_ocr" if self.ocr_error == "no_ocr" else "err_ocr"), 3500)

    def _when_ocr_ready(self, *action) -> bool:
        """Run `action` now if OCR is done, otherwise queue it. Returns True if it was queued."""
        if self.ocr_error:
            self._show_ocr_error()
            return True
        if self.ocr_done:
            return False
        self.pending_action = action
        self.pill.show_progress(i18n.tr("reading"), None)
        return True

    # ------------------------------------------------------------ translation
    def translate_all(self) -> None:
        if self._when_ocr_ready(self.translate_all):
            return
        if not self.blocks:
            self.pill.show_message(i18n.tr("no_text"), 2000)
            return
        self.translate_blocks(self.blocks)

    def handle_gesture(self, gesture: Gesture) -> None:
        if self._when_ocr_ready(self.handle_gesture, gesture):
            return
        if gesture.kind == "click":
            x, y = gesture.points[0]
            item = self._item_at(x, y)
            if item is not None and item.status == "done":
                self._copy_item(item)
                return
            block = block_at(self.blocks, x, y)
            if block is not None:
                self.translate_blocks([block])
            elif self.state in (State.TRANSLATING, State.SHOWING):
                self.close_overlay()
            else:
                self.pill.show_message(i18n.tr("no_text"), 2000)
            return
        chosen = select_blocks(self.blocks, gesture)
        if chosen:
            self.translate_blocks(chosen)
        else:
            self.pill.show_message(i18n.tr("no_text"), 2000)

    def _make_item(self, block: Block) -> Item:
        bgra = self.capture.bgra
        cover = block.cover_rect()
        bg = sample_background(bgra, cover)
        fg = sample_text_color(bgra, block.rect, bg)
        boxed = len(block.lines) == 1 and is_boxed(bgra, cover, bg, block.line_height)
        weight = weight_class(stroke_ratio(bgra, block.rect, bg, fg, block.font_px))
        extra = 0.0
        if len(block.lines) == 1 and not boxed:
            free = free_space_right(bgra, cover, bg, block.rect.w * 2)
            extra = max(0.0, free - block.font_px * 0.6)
        button = button_shape(bgra, block.rect, bg, block.line_height) if boxed else None
        below = 0.0 if boxed else free_space_below(bgra, cover, bg, cover.h * 1.5)
        item = Item(block.id, block, frozenset(id(l) for l in block.lines), QColor(*bg), QColor(*fg), boxed,
                    weight=weight, extra_w=extra, t_added=self.now())
        item.meta["free_below"] = below
        item.meta["button"] = button
        return item

    def _usable_language(self, block: Block, tgt: str) -> str:
        """Avoid downloading a model because of an unsure guess: if the detected language has no
        installed model and the evidence is weak (short text, probability < 0.9), use the most
        likely language among those that can already be translated (or the target itself)."""
        lang = block.lang or self.screen_lang or "en"
        translator = getattr(self.engine, "translator", None)
        if translator is None or lang == tgt:
            return lang
        from ..translate import langdetect
        from ..translate.translator import route

        def ready(src: str) -> bool:
            return src == tgt or all(translator.store.get(*p) for p in route(src, tgt))

        if ready(lang):
            return lang
        probs = langdetect.scores(block.text)
        if probs.get(lang, 0.0) >= 0.9 or len(block.text.split()) >= 8:
            return lang  # clear evidence: worth downloading the model
        usable = {code: p for code, p in probs.items() if ready(code)}
        return max(usable, key=usable.get) if usable else lang

    def translate_blocks(self, blocks: list[Block]) -> None:
        tgt = self.target
        new: list[Item] = []
        for b in blocks:
            ids = frozenset(id(l) for l in b.lines)
            if any(ids <= it.line_ids for it in self.items.values() if it.status != "error"):
                continue
            for k, it in list(self.items.items()):
                if it.line_ids <= ids:
                    del self.items[k]
            new.append(self._make_item(b))
        if not new:
            return
        for it in new:
            it.block.lang = self._usable_language(it.block, tgt)
        todo = [it for it in new if (it.block.lang or self.screen_lang) != tgt and not looks_untranslatable(it.block.text)]
        if not todo:
            if not any(it.status == "done" for it in self.items.values()):
                self.pill.show_message(i18n.tr("already_in", lang=i18n.lang_name(tgt)), 2500)
            return
        for it in todo:
            it.status = "pending"
            self.items[it.key] = it
        langs = Counter(it.block.lang or self.screen_lang or "en" for it in todo)
        try:
            from ..ocr import backend as ocr_backend

            available = set(ocr_backend().available_languages())
            for lang in langs:
                if available and lang not in available:
                    self.ocr_pack_missing.emit(lang)
        except Exception:  # noqa: BLE001 - only a hint for the user
            pass
        self.pill.set_languages(langs.most_common(1)[0][0], tgt)
        self.pill.set_original_shown(False)
        self.show_original = False
        self.pill.set_mode("result")
        self.state = State.TRANSLATING
        jobs = [TranslationJob(it.key, it.block.text, it.block.lang or self.screen_lang or "en") for it in todo]
        self._t_request = time.perf_counter()
        self.engine.translate(self.session, jobs, tgt)

    def _fit(self, item: Item) -> FitResult:
        b = item.block
        pad = b.cover_rect().x - b.rect.x  # negative pad
        area = b.rect.adjusted(pad * 0.5, pad * 0.3, -pad * 0.5, -pad * 0.3)
        if len(b.lines) > 1:
            pitch = (b.lines[-1].rect.y - b.lines[0].rect.y) / (len(b.lines) - 1)
            spacing = max(1.1, min(1.6, pitch / b.font_px))
        else:
            spacing = 1.2
        min_px = min(MIN_TEXT_PX * self.scale, b.font_px)
        # Room for the same number of lines at the original size, even if the OCR box is
        # shorter (a line without ascenders or descenders has a short box).
        height = max(area.h, len(b.lines) * b.font_px * spacing)
        measure = lambda text, px: self._measure(text, px, item.weight)  # noqa: E731
        button = item.meta.get("button")
        item.meta["box"] = None
        if button is not None:
            # Buttons: use their inside; if the translation still does not fit at a legible
            # size, widen the button background sideways (over free room) before shrinking.
            r = button.rect
            pad = max(b.font_px * 0.6, min(b.rect.x - r.x, r.right - b.rect.right))
            inner = r.w - 2 * pad
            need = measure(item.text, b.font_px)  # grow for the original size if there is room
            grow = 0.0
            if need > inner:
                room = 2 * max(0.0, min(button.room_left, button.room_right) - 4 * self.scale)
                grow = max(0.0, min(need - inner, room, r.w))
            item.meta["box"] = (Rect(r.x - grow / 2, r.y, r.w + grow, r.h), button.radius)
            return fit_text(item.text, inner + grow, height, b.font_px, min_px, measure,
                            line_spacing=spacing, max_grow=1.0)
        # The background may grow down only over free background (never over other text).
        grow = 1.0 + max(0.0, item.meta.get("free_below", 0.0) - b.font_px * 0.3) / max(height, 1.0)
        return fit_text(item.text, area.w + item.extra_w, height, b.font_px, min_px, measure,
                        line_spacing=spacing, max_grow=max(1.0, min(1.6, grow)))

    def _on_translated(self, session: int, key: int, text: str) -> None:
        if session != self.session:
            return
        item = self.items.get(key)
        if item is None:
            return
        item.text = text
        try:
            item.fit = self._fit(item)
            item.layout = self._layout_text(item)
        except Exception:  # noqa: BLE001
            log.exception("Fitting failed")
            item.status = "error"
            return
        item.status = "done"
        item.t_done = self.now()
        if getattr(self, "_t_request", None):
            log.info("First block on screen %.0f ms after the translation request (%.0f ms after hotkey)",
                     (time.perf_counter() - self._t_request) * 1000, (time.perf_counter() - self._t_hotkey) * 1000)
            self._t_request = None
        if self.pill.mode() == "progress":
            self.pill.end_message()

    def _on_translation_finished(self, session: int, seconds: float) -> None:
        if session != self.session or self.state == State.IDLE:
            return
        if not any(it.status == "pending" for it in self.items.values()):
            self.state = State.SHOWING if any(it.status == "done" for it in self.items.values()) else State.READY
            if self.pill.mode() == "progress":
                self.pill.end_message()

    def _on_translation_failed(self, session: int, kind: str, keys) -> None:
        if session != self.session or self.state == State.IDLE:
            return
        for k in keys:
            self.items.pop(k, None)
        msg = {"network": "err_network", "disk": "err_disk", "unavailable": "err_translate"}.get(kind, "err_translate")
        if not self.items:
            self.state = State.READY
            self.pill.set_mode("ready")
        self.pill.show_message(i18n.tr(msg), 4000)

    def _on_progress(self, session: int, kind: str, fraction: float) -> None:
        if session != self.session or self.state == State.IDLE:
            return
        if kind == "download":
            self.pill.show_progress(i18n.tr("downloading", pct=int(fraction * 100)), fraction)
        else:
            self.pill.show_progress(i18n.tr("loading_model"), None)

    def set_target(self, code: str) -> None:
        self.menu.hide()
        if code == self.target:
            return
        self.target = code
        self.target_changed.emit(code)
        blocks = [it.block for it in sorted(self.items.values(), key=lambda i: i.key) if it.status != "error"]
        self.items.clear()
        if blocks:
            self.translate_blocks(blocks)
        else:
            self.pill.set_languages(self.screen_lang, code)

    # --------------------------------------------------------------- copying
    def _ordered_items(self) -> list[Item]:
        return sorted((it for it in self.items.values() if it.status == "done"),
                      key=lambda it: (round(it.block.rect.y / 8), it.block.rect.x))

    def copy_all(self) -> None:
        items = self._ordered_items()
        if not items:
            return
        showing_original = self.show_original or self.space_held
        text = "\n\n".join(it.block.text if showing_original else it.text for it in items)
        QGuiApplication.clipboard().setText(text)
        self.pill.flash_copied()

    def _copy_item(self, item: Item) -> None:
        original = self.show_original or self.space_held
        QGuiApplication.clipboard().setText(item.block.text if original else item.text)
        r = self.to_logical(item.block.cover_rect())
        self.toasts.append((i18n.tr("copied"), QPointF(r.center().x(), r.top()), self.now()))

    def toggle_original(self) -> None:
        self.show_original = not self.show_original
        self.pill.set_original_shown(self.show_original)

    def _item_at(self, x: float, y: float) -> Item | None:
        hits = [it for it in self.items.values() if self._item_rect(it).contains(x, y)]
        return min(hits, key=lambda it: it.block.rect.w * it.block.rect.h) if hits else None

    def _item_rect(self, it: Item) -> Rect:
        if it.layout is not None:
            box = it.layout[2]
            s = self.scale
            return Rect(box.x() * s, box.y() * s, box.width() * s, box.height() * s)
        return it.block.cover_rect()

    def _toggle_menu(self) -> None:
        if self.menu.isVisible():
            self.menu.hide()
        else:
            self.menu.set_current(self.target)
            self.menu.show()
            self._place_menu()
            self.menu.raise_()

    # ---------------------------------------------------------------- input
    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key_Escape:
            if self.menu.isVisible():
                self.menu.hide()
            else:
                self.close_overlay()
        elif k in (Qt.Key_Return, Qt.Key_Enter):
            self.translate_all()
        elif k == Qt.Key_Space:
            if not e.isAutoRepeat():
                self.space_held = True
        elif k == Qt.Key_C and e.modifiers() & Qt.ControlModifier:
            self.copy_all()
        else:
            super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key_Space and not e.isAutoRepeat():
            self.space_held = False
        else:
            super().keyReleaseEvent(e)

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            if e.button() == Qt.RightButton:
                self.close_overlay()
            return
        if self.menu.isVisible():
            self.menu.hide()
            return
        self.dragging = True
        self.stroke = [e.position()]
        self.stroke_fade_from = -1.0

    def mouseMoveEvent(self, e):
        pos = e.position()
        if self.dragging:
            last = self.stroke[-1]
            if (pos - last).manhattanLength() >= 1.5:
                self.stroke.append(pos)
            return
        x, y = self.to_phys(pos)
        over = self._item_at(x, y) is not None or (self.ocr_done and block_at(self.blocks, x, y) is not None)
        self.setCursor(Qt.PointingHandCursor if over else Qt.ArrowCursor)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self.dragging:
            return
        self.dragging = False
        points = [self.to_phys(p) for p in self.stroke]
        gesture = classify(points, click_tolerance=6 * self.scale)
        if gesture.kind != "click":
            self.last_stroke_path = self._stroke_shape(gesture)
            self.stroke_fade_from = self.now()
        self.stroke = []
        self.handle_gesture(gesture)

    def changeEvent(self, e):
        if e.type() == QEvent.ActivationChange and self.state != State.IDLE:
            if self.isActiveWindow():
                self._was_active = True
            elif self._was_active:
                QTimer.singleShot(0, self._close_if_inactive)
        super().changeEvent(e)

    def _close_if_inactive(self) -> None:
        if not self.isActiveWindow() and self.state != State.IDLE:
            log.info("Overlay lost focus, closing")
            self.close_overlay()

    # ------------------------------------------------------------- animation
    def _tick(self) -> None:
        t = self.now()
        target_dim = 0.30 if self.state == State.READY else (0.12 if self.state == State.TRANSLATING else 0.0)
        self.dim += (target_dim - self.dim) * 0.18
        if abs(target_dim - self.dim) < 0.002:
            self.dim = target_dim
        self.glow.level += ((1.0 if self.state == State.READY else 0.55) - self.glow.level) * 0.12
        want = 1.0 if (self.show_original or self.space_held) else 0.0
        self.original_mix += (want - self.original_mix) * 0.35
        if t < 440:
            self.place_pill()
        self.toasts = [ts for ts in self.toasts if t - ts[2] < 1300]
        self.update()

    def _stroke_shape(self, gesture: Gesture) -> QPainterPath:
        if gesture.kind == "rect":
            path = QPainterPath()
            path.addRoundedRect(self.to_logical(gesture.rect), 10, 10)
            return path
        path = effects.smooth_path([QPointF(x / self.scale, y / self.scale) for x, y in gesture.points])
        path.closeSubpath()
        return path

    # -------------------------------------------------------------- painting
    def paintEvent(self, e):
        if self.pixmap is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        t = self.now()
        full = QRectF(self.rect())
        p.drawPixmap(0, 0, self.pixmap)
        ordered = sorted(self.items.values(), key=lambda i: i.block.rect.w * i.block.rect.h, reverse=True)
        # Translations go under the dimming so they always blend with their surroundings;
        # pending blocks go above it, which highlights what is being translated.
        for it in ordered:
            if it.status == "done":
                self._paint_item(p, it, t)
        if self.dim > 0.002:
            p.fillRect(full, QColor(0, 0, 0, int(255 * self.dim)))
        for it in ordered:
            if it.status != "done":
                self._paint_item(p, it, t)
        if self.debug_blocks:
            self._paint_debug(p)
        self._paint_stroke(p, t)
        self.glow.paint(p, full, t, GLOW_PX)
        self._paint_toasts(p, t)
        p.end()
        if not self._first_paint_logged and self.state != State.IDLE:
            self._first_paint_logged = True
            log.info("Overlay visible %.0f ms after hotkey (first frame painted)",
                     (time.perf_counter() - self._t_hotkey) * 1000)

    def _paint_item(self, p: QPainter, it: Item, t: float) -> None:
        cover = self.to_logical(self._item_rect(it))
        box = it.meta.get("box") if it.status == "done" else None
        radius = box[1] / self.scale if box else min(6.0, cover.height() / 4)
        if it.status == "pending":
            appear = effects.ease_out_cubic((t - it.t_added) / 180)
            effects.paint_shimmer(p, cover, radius, it.bg, t, appear)
            return
        if it.status != "done" or it.layout is None:
            return
        fade = effects.ease_out_cubic((t - it.t_done) / FADE_MS)
        if fade < 1:
            effects.paint_shimmer(p, self.to_logical(it.block.cover_rect()), min(6.0, cover.height() / 4),
                                  it.bg, t, 1 - fade)
        alpha = fade * (1 - self.original_mix)
        if alpha <= 0.01:
            return
        p.save()
        p.setOpacity(alpha)
        path = QPainterPath()
        path.addRoundedRect(cover, radius, radius)
        p.fillPath(path, it.bg)
        self._paint_text(p, it)
        p.restore()

    def _layout_text(self, it: Item) -> tuple:
        """Place each wrapped line (logical px) and compute the background box that covers
        both the original text and the translation."""
        fit = it.fit
        b = it.block
        font, fm = self._font(fit.px, it.weight)
        s = self.scale
        box = it.meta.get("box")
        cover = self.to_logical(box[0] if box else b.cover_rect())
        area = self.to_logical(b.rect)
        lh = fit.line_height / s
        em0 = b.font_px
        if len(b.lines) == 1 and len(fit.lines) > 1:
            # One original line wrapped into several: centre them on it, growing downwards.
            centre = (b.baseline - 0.36 * em0) / s
            first = centre - (len(fit.lines) - 1) * lh / 2 + 0.36 * fit.px / s
            first = max(first, cover.top() + fm.ascent() * 0.78)
        else:
            # Same baseline as the original, nudged so the x-height stays centred when shrinking.
            first = (b.baseline - (em0 - fit.px) * 0.36) / s
        placed = []
        left, right = cover.left(), cover.right()
        for i, line in enumerate(fit.lines):
            w = fm.horizontalAdvance(line)
            x = cover.center().x() - w / 2 if it.boxed else area.left()
            placed.append((x, first + i * lh, line))
            left, right = min(left, x - 2), max(right, x + w + 2)
        top = min(cover.top(), first - fm.ascent() * 0.8 - 2)
        bottom = max(cover.bottom(), first + (len(fit.lines) - 1) * lh + fm.descent() + 2)
        return font, placed, QRectF(left, top, right - left, bottom - top)

    def _paint_text(self, p: QPainter, it: Item) -> None:
        font, placed, _ = it.layout
        p.setFont(font)
        p.setPen(it.fg)
        for x, y, line in placed:
            p.drawText(QPointF(x, y), line)

    def _paint_stroke(self, p: QPainter, t: float) -> None:
        center = QPointF(self.width() / 2, self.height() / 2)
        angle = self.glow.angle(t)
        start = self.stroke[0] if self.stroke else (self.last_stroke_path.pointAtPercent(0)
                                                    if self.last_stroke_path is not None else QPointF())
        light = self.glow.is_light_at(start.x(), start.y())
        if self.dragging and len(self.stroke) > 1:
            points = [self.to_phys(q) for q in self.stroke]
            g = classify(points, click_tolerance=6 * self.scale)
            if g.kind == "rect":
                r = self.to_logical(g.rect)
                fill = QColor(255, 255, 255, 28)
                path = QPainterPath()
                path.addRoundedRect(r, 10, 10)
                p.fillPath(path, fill)
                effects.paint_stroke(p, path, center, angle, STROKE_PX, 0.55, light_bg=light)
                effects.paint_stroke(p, effects.smooth_path(self.stroke), center, angle, STROKE_PX * 0.75, 0.6,
                                     light_bg=light)
            else:
                effects.paint_stroke(p, effects.smooth_path(self.stroke), center, angle, STROKE_PX, light_bg=light)
        elif self.last_stroke_path is not None and self.stroke_fade_from >= 0:
            k = 1 - (t - self.stroke_fade_from) / 380
            if k <= 0:
                self.last_stroke_path = None
            else:
                effects.paint_stroke(p, self.last_stroke_path, center, angle, STROKE_PX, effects.ease_in_out(k),
                                     light_bg=light)

    def _paint_toasts(self, p: QPainter, t: float) -> None:
        if not self.toasts:
            return
        font = ui_font(13, QFont.DemiBold)
        fm = QFontMetricsF(font)
        theme = self.pill.theme
        for text, pos, t0 in self.toasts:
            age = t - t0
            a = effects.ease_out_cubic(age / 120) * (1 - effects.ease_in_out((age - 900) / 400) if age > 900 else 1)
            w = fm.horizontalAdvance(text) + 28
            h = 30.0
            r = QRectF(pos.x() - w / 2, pos.y() - h - 8 - 6 * effects.ease_out_cubic(age / 200), w, h)
            r.moveTop(max(4.0, r.top()))
            p.save()
            p.setOpacity(max(0.0, a))
            path = QPainterPath()
            path.addRoundedRect(r, h / 2, h / 2)
            p.fillPath(path, theme.bg)
            p.setPen(QPen(theme.border, 1))
            p.drawPath(path)
            p.setPen(theme.text)
            p.setFont(font)
            p.drawText(r, Qt.AlignCenter, text)
            p.restore()

    def _paint_debug(self, p: QPainter) -> None:
        p.save()
        f = ui_font(11, QFont.DemiBold)
        p.setFont(f)
        for b in self.blocks:
            r = self.to_logical(b.rect)
            p.setPen(QPen(QColor(255, 0, 120), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawRect(r)
            for line in b.lines:
                p.setPen(QPen(QColor(0, 200, 255, 160), 1, Qt.DotLine))
                p.drawRect(self.to_logical(line.rect))
            label = f"{b.id} {b.lang}"
            p.fillRect(QRectF(r.left(), r.top() - 15, 8 * len(label) + 6, 15), QColor(255, 0, 120))
            p.setPen(QColor(255, 255, 255))
            p.drawText(QPointF(r.left() + 3, r.top() - 3), label)
        p.restore()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.capture is not None:
            self.scale = self.devicePixelRatioF()
            if self.pixmap is not None:
                self.pixmap.setDevicePixelRatio(self.scale)
            self._fonts.clear()
        self.place_pill()
