"""About window: version and the credits required by model and library licenses."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout

from . import __version__, credits, i18n
from .icon import app_icon
from .paths import licenses_dir
from .platform import services


class AboutDialog(QDialog):
    def __init__(self):
        super().__init__(None, Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setWindowTitle(i18n.tr("tray_about"))
        self.setWindowIcon(app_icon())
        lay = QVBoxLayout(self)
        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(48, 48))
        title = QLabel(f"<b style='font-size:16pt'>KeepT</b> {__version__}<br>{i18n.tr('about_intro')}")
        title.setWordWrap(True)
        head.addWidget(logo)
        head.addWidget(title, 1)
        lay.addLayout(head)
        text = QTextBrowser()
        text.setOpenExternalLinks(True)
        text.setHtml(credits.as_html(i18n.tr))
        lay.addWidget(text, 1)
        buttons = QHBoxLayout()
        folder = QPushButton(i18n.tr("about_licenses_folder"))
        folder.clicked.connect(lambda: services().open_folder(licenses_dir()))
        close = QPushButton("OK")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        buttons.addWidget(folder)
        buttons.addStretch(1)
        buttons.addWidget(close)
        lay.addLayout(buttons)
        self.resize(560, 620)
