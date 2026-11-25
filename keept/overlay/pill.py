"""Floating pill at the bottom of the overlay: "Translate screen", languages, Copy, Original."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontDatabase, QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .. import i18n
from . import effects

SHADOW = 14  # logical px around the pill reserved for the soft shadow
IconPainter = Callable[[QPainter, QRectF, QColor], None]


def ui_font(px: float = 14, weight: QFont.Weight = QFont.Normal) -> QFont:
    families = set(QFontDatabase.families())
    family = "Segoe UI Variable Text" if "Segoe UI Variable Text" in families else "Segoe UI"
    f = QFont(family)
    f.setPixelSize(int(px))
    f.setWeight(weight)
    f.setHintingPreference(QFont.PreferNoHinting)
    return f


class Theme:
    def __init__(self, dark: bool):
        self.dark = dark
        if dark:
            self.bg = QColor(36, 36, 40, 232)
            self.border = QColor(255, 255, 255, 28)
            self.text = QColor(244, 244, 246)
            self.muted = QColor(190, 190, 198)
            self.hover = QColor(255, 255, 255, 26)
            self.press = QColor(255, 255, 255, 44)
            self.primary = QColor(255, 255, 255, 20)
        else:
            self.bg = QColor(250, 250, 252, 238)
            self.border = QColor(0, 0, 0, 22)
            self.text = QColor(28, 28, 32)
            self.muted = QColor(92, 92, 100)
            self.hover = QColor(0, 0, 0, 14)
            self.press = QColor(0, 0, 0, 28)
            self.primary = QColor(0, 0, 0, 8)


class PillButton(QWidget):
    clicked = Signal()

    def __init__(self, theme: Theme, text: str = "", icon: IconPainter | None = None,
                 trailing: IconPainter | None = None, bold: bool = False, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._text = text
        self._icon = icon
        self._trailing = trailing
        self._hover = False
        self._down = False
        self._font = ui_font(14, QFont.DemiBold if bold else QFont.Medium)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)

    def set_text(self, text: str) -> None:
        self._text = text
        self.updateGeometry()
        self.update()

    def set_icon(self, icon: IconPainter | None) -> None:
        self._icon = icon
        self.updateGeometry()
        self.update()

    def text(self) -> str:
        return self._text

    def sizeHint(self) -> QSize:
        fm = QFontMetricsF(self._font)
        w = 16.0 + fm.horizontalAdvance(self._text) + 16.0
        if self._icon:
            w += 18 + 8
        if self._trailing:
            w += 12 + 6
        if not self._text:
            w = 40
        return QSize(int(w + 0.5), 40)

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self._down = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._down = True
            self.update()
        e.accept()

    def mouseReleaseEvent(self, e):
        was = self._down
        self._down = False
        self.update()
        e.accept()
        if was and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        bg = self.theme.press if self._down else (self.theme.hover if self._hover else None)
        if bg is not None:
            path = QPainterPath()
            path.addRoundedRect(r, r.height() / 2, r.height() / 2)
            p.fillPath(path, bg)
        x = 16.0 if self._text else (r.width() - 18) / 2 + 1
        cy = r.center().y()
        if self._icon:
            self._icon(p, QRectF(x, cy - 9, 18, 18), self.theme.text)
            x += 18 + 8
        if self._text:
            p.setFont(self._font)
            p.setPen(self.theme.text)
            fm = QFontMetricsF(self._font)
            tw = fm.horizontalAdvance(self._text)
            p.drawText(QRectF(x, r.top(), tw + 2, r.height()), Qt.AlignVCenter | Qt.AlignLeft, self._text)
            x += tw + 6
        if self._trailing:
            self._trailing(p, QRectF(x, cy - 6, 12, 12), self.theme.muted)


class Separator(QWidget):
    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.setFixedSize(9, 40)

    def paintEvent(self, e):
        p = QPainter(self)
        c = QColor(self.theme.text)
        c.setAlpha(40)
        p.setPen(QPen(c, 1))
        p.drawLine(QPointF(4.5, 12), QPointF(4.5, 28))


class Pill(QWidget):
    """Modes: ready, result, message, progress."""

    translate_all = Signal()
    copy_all = Signal()
    toggle_original = Signal()
    open_languages = Signal()

    def __init__(self, dark: bool, parent=None):
        super().__init__(parent)
        self.theme = Theme(dark)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self._mode = "ready"
        self._restore_mode = "ready"
        self._progress: float | None = None
        self._message = ""
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._end_message)

        t = self.theme
        self.btn_translate = PillButton(t, i18n.tr("translate_screen"), effects.icon_sparkle, bold=True)
        self.btn_lang = PillButton(t, "", None, trailing=effects.icon_chevron)
        self.sep = Separator(t)
        self.btn_copy = PillButton(t, i18n.tr("copy"), effects.icon_copy)
        self.btn_toggle = PillButton(t, i18n.tr("show_original"), effects.icon_eye)
        self.lbl = PillButton(t, "")
        self.lbl.setCursor(Qt.ArrowCursor)
        self.lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        lay = QHBoxLayout(self)
        m = SHADOW + 6
        lay.setContentsMargins(m, m, m, m)
        lay.setSpacing(2)
        for w in (self.btn_translate, self.btn_lang, self.sep, self.btn_copy, self.btn_toggle, self.lbl):
            lay.addWidget(w)

        self.btn_translate.clicked.connect(self.translate_all)
        self.btn_copy.clicked.connect(self.copy_all)
        self.btn_toggle.clicked.connect(self.toggle_original)
        self.btn_lang.clicked.connect(self.open_languages)
        self.set_mode("ready")

    # -- content ---------------------------------------------------------------
    def set_theme(self, dark: bool) -> None:
        if dark == self.theme.dark:
            return
        new = Theme(dark)
        self.theme.__dict__.update(new.__dict__)
        self.update()

    def set_languages(self, src: str | None, tgt: str) -> None:
        src_name = i18n.lang_name(src) if src else ""
        text = f"{src_name}  →  {i18n.lang_name(tgt)}" if src_name else i18n.lang_name(tgt)
        self.btn_lang.set_text(text)

    def set_original_shown(self, shown: bool) -> None:
        self.btn_toggle.set_text(i18n.tr("show_translation") if shown else i18n.tr("show_original"))

    def flash_copied(self) -> None:
        self.btn_copy.set_text(i18n.tr("copied"))
        self.btn_copy.set_icon(effects.icon_check)
        QTimer.singleShot(1200, self._reset_copy)
        self._relayout()

    def _reset_copy(self) -> None:
        self.btn_copy.set_text(i18n.tr("copy"))
        self.btn_copy.set_icon(effects.icon_copy)
        self._relayout()

    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        self._timer.stop()
        self._mode = mode
        if mode in ("ready", "result"):
            self._restore_mode = mode
            self._progress = None
        ready, result, text = mode == "ready", mode == "result", mode in ("message", "progress")
        self.btn_translate.setVisible(ready)
        for w in (self.btn_lang, self.sep, self.btn_copy, self.btn_toggle):
            w.setVisible(result)
        self.lbl.setVisible(text)
        self._relayout()

    def show_message(self, text: str, timeout_ms: int = 2000) -> None:
        self._message = text
        self.lbl.set_text(text)
        self._progress = None
        self.set_mode("message")
        if timeout_ms > 0:
            self._timer.start(timeout_ms)

    def show_progress(self, text: str, fraction: float | None) -> None:
        self.lbl.set_text(text)
        self._progress = fraction
        if self._mode != "progress":
            self.set_mode("progress")
        self.update()

    def end_message(self) -> None:
        if self._mode in ("message", "progress"):
            self._end_message()

    def _end_message(self) -> None:
        self.set_mode(self._restore_mode)

    def _relayout(self) -> None:
        self.layout().activate()
        self.adjustSize()
        parent = self.parentWidget()
        if parent is not None and hasattr(parent, "place_pill"):
            parent.place_pill()
        self.update()

    def pill_rect(self) -> QRectF:
        return QRectF(self.rect()).adjusted(SHADOW, SHADOW, -SHADOW, -SHADOW)

    # -- painting ----------------------------------------------------------------
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.pill_rect()
        rad = r.height() / 2
        # Soft shadow: stacked translucent rounded rects.
        for i in range(SHADOW, 0, -2):
            a = int(26 * (1 - i / SHADOW) ** 2) + 1
            sh = QPainterPath()
            rr = r.adjusted(-i * 0.6, -i * 0.35, i * 0.6, i * 0.9)
            sh.addRoundedRect(rr, rad + i * 0.6, rad + i * 0.6)
            p.fillPath(sh, QColor(0, 0, 0, a))
        path = QPainterPath()
        path.addRoundedRect(r, rad, rad)
        p.fillPath(path, self.theme.bg)
        p.setPen(QPen(self.theme.border, 1))
        p.drawPath(path)
        if self._mode == "progress" and self._progress is not None:
            track = QRectF(r.left() + rad, r.bottom() - 7, r.width() - 2 * rad, 3)
            c = QColor(self.theme.text)
            c.setAlpha(30)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(track, 1.5, 1.5)
            fill = QRectF(track)
            fill.setWidth(track.width() * max(0.0, min(1.0, self._progress)))
            p.setBrush(QBrush(effects.brand_gradient(fill)))
            p.drawRoundedRect(fill, 1.5, 1.5)


class LangMenu(QWidget):
    """Small list of target languages shown above the pill (no system popup)."""

    chosen = Signal(str)

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._buttons: dict[str, PillButton] = {}
        lay = QVBoxLayout(self)
        m = SHADOW + 6
        lay.setContentsMargins(m, m, m, m)
        lay.setSpacing(0)
        for code in ("de", "en", "es"):
            b = PillButton(theme, i18n.lang_name(code))
            b.clicked.connect(lambda c=code: self.chosen.emit(c))
            lay.addWidget(b)
            self._buttons[code] = b
        self.hide()

    def set_current(self, code: str) -> None:
        for c, b in self._buttons.items():
            b.set_icon(effects.icon_check if c == code else _blank)
        self.layout().activate()
        self.adjustSize()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(SHADOW, SHADOW, -SHADOW, -SHADOW)
        for i in range(SHADOW, 0, -2):
            a = int(26 * (1 - i / SHADOW) ** 2) + 1
            sh = QPainterPath()
            sh.addRoundedRect(r.adjusted(-i * 0.6, -i * 0.35, i * 0.6, i * 0.9), 20 + i * 0.6, 20 + i * 0.6)
            p.fillPath(sh, QColor(0, 0, 0, a))
        path = QPainterPath()
        path.addRoundedRect(r, 20, 20)
        p.fillPath(path, self.theme.bg)
        p.setPen(QPen(self.theme.border, 1))
        p.drawPath(path)


def _blank(p: QPainter, r: QRectF, c: QColor) -> None:
    pass
