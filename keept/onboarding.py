"""First run: a floating pill that asks once which language to translate into.

Not a dialog: a non modal, frameless pill at the bottom of the primary monitor
with three buttons (Deutsch, English, Español), in the style of the overlay pill.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QWidget

from . import i18n
from .overlay import effects
from .overlay.pill import SHADOW, PillButton, Separator, Theme, ui_font

ENDONYMS = (("de", "Deutsch"), ("en", "English"), ("es", "Español"))


class _Label(QWidget):
    def __init__(self, theme: Theme, text: str, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.text = text
        self.font = ui_font(14, QFont.DemiBold)
        w = QFontMetricsF(self.font).horizontalAdvance(text)
        self.setFixedSize(int(w + 16 + 26 + 8), 40)

    def set_text(self, text: str) -> None:
        self.text = text
        w = QFontMetricsF(self.font).horizontalAdvance(text)
        self.setFixedSize(int(w + 16 + 26 + 8), 40)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        effects.icon_sparkle(p, QRectF(14, 11, 18, 18), self.theme.text)
        p.setFont(self.font)
        p.setPen(self.theme.text)
        p.drawText(QRectF(42, 0, self.width() - 42, 40), Qt.AlignVCenter | Qt.AlignLeft, self.text)


class LanguagePrompt(QWidget):
    chosen = Signal(str)

    def __init__(self, dark: bool, suggested: str):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.NoDropShadowWindowHint)
        self.setWindowTitle("KeepT setup")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.theme = Theme(dark)
        # A floating window over arbitrary content needs a more opaque background than the
        # overlay pill (which always sits on the frozen, dimmed screenshot).
        self.theme.bg.setAlpha(250)
        self.label = _Label(self.theme, i18n.tr("onboard_title"))
        lay = QHBoxLayout(self)
        m = SHADOW + 6
        lay.setContentsMargins(m, m, m, m)
        lay.setSpacing(2)
        lay.addWidget(self.label)
        lay.addWidget(Separator(self.theme))
        self.buttons: dict[str, PillButton] = {}
        for code, name in ENDONYMS:
            b = PillButton(self.theme, name, bold=(code == suggested))
            b.clicked.connect(lambda c=code: self._choose(c))
            lay.addWidget(b)
            self.buttons[code] = b
        self.adjustSize()

    def show_at_bottom(self) -> None:
        screen = QGuiApplication.primaryScreen().availableGeometry()
        x = screen.center().x() - self.width() // 2
        y = screen.bottom() - self.height() - 24 + SHADOW
        self.move(x, y + 40)
        self.setWindowOpacity(0.0)
        self.show()
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(380)
        self._anim.setStartValue(QPoint(x, y + 40))
        self._anim.setEndValue(QPoint(x, y))
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(260)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.finished.connect(lambda: self.setWindowOpacity(1.0))
        self._anim.start()
        self._fade.start()

    def _choose(self, code: str) -> None:
        for b in self.buttons.values():
            b.setEnabled(False)
        self.chosen.emit(code)

    def confirm(self, text: str) -> None:
        """Replace the question by a short confirmation, then go away."""
        for b in self.buttons.values():
            b.hide()
        self.findChild(Separator).hide()
        self.label.set_text(text)
        self.layout().activate()
        old_center = self.geometry().center()
        self.adjustSize()
        self.move(old_center.x() - self.width() // 2, self.y())
        QTimer.singleShot(3500, self._fade_out)

    def _fade_out(self) -> None:
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(300)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self.close)
        self._fade.start()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(SHADOW, SHADOW, -SHADOW, -SHADOW)
        rad = r.height() / 2
        for i in range(SHADOW, 0, -2):
            a = int(30 * (1 - i / SHADOW) ** 2) + 1
            sh = QPainterPath()
            sh.addRoundedRect(r.adjusted(-i * 0.6, -i * 0.35, i * 0.6, i * 0.9), rad + i * 0.6, rad + i * 0.6)
            p.fillPath(sh, QColor(0, 0, 0, a))
        path = QPainterPath()
        path.addRoundedRect(r, rad, rad)
        p.fillPath(path, self.theme.bg)
        p.setPen(QPen(self.theme.border, 1))
        p.drawPath(path)
