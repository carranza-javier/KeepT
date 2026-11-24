"""System tray icon and its menu (settings live here, there is no main window)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QDialog, QLabel, QMenu, QSystemTrayIcon, QVBoxLayout

from . import i18n
from .hotkey import PRESETS, Hotkey
from .icon import app_icon
from .platform import services

if TYPE_CHECKING:
    from .app import KeepTApp

log = logging.getLogger(__name__)


class HotkeyDialog(QDialog):
    """Captures a new key combination. Only used from the tray settings, never in the main flow."""

    def __init__(self):
        super().__init__(None, Qt.WindowStaysOnTopHint | Qt.Dialog)
        self.setWindowTitle(i18n.tr("hotkey_dialog_title"))
        self.setWindowIcon(app_icon())
        self.result_text: str | None = None
        lay = QVBoxLayout(self)
        self.label = QLabel(i18n.tr("hotkey_dialog_body"))
        self.label.setWordWrap(True)
        self.preview = QLabel("")
        self.preview.setAlignment(Qt.AlignCenter)
        f = self.preview.font()
        f.setPointSize(16)
        f.setBold(True)
        self.preview.setFont(f)
        lay.addWidget(self.label)
        lay.addWidget(self.preview)
        self.resize(380, 140)

    def keyPressEvent(self, e):
        key = e.key()
        if key == Qt.Key_Escape:
            self.reject()
            return
        if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta, Qt.Key_AltGr):
            return
        mods = []
        m = e.modifiers()
        if m & Qt.ControlModifier:
            mods.append("Ctrl")
        if m & Qt.AltModifier:
            mods.append("Alt")
        if m & Qt.ShiftModifier:
            mods.append("Shift")
        if m & Qt.MetaModifier:
            mods.append("Win")
        name = QKeySequence(key).toString()
        try:
            hk = Hotkey.parse("+".join([*mods, name]))
        except ValueError:
            self.preview.setText("+".join([*mods, name]) + "  ✕")
            return
        if hk.conflicts_with_game_bar:
            self.preview.setText(str(hk) + "  ✕ (Game Bar)")
            return
        self.result_text = str(hk)
        self.preview.setText(self.result_text)
        self.accept()


class Tray:
    def __init__(self, app: "KeepTApp"):
        self.app = app
        self.icon = QSystemTrayIcon(app_icon())
        self.icon.activated.connect(self._on_activated)
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self.rebuild)
        self.icon.setContextMenu(self.menu)
        self._status = ""
        self.update_tooltip()
        self.rebuild()
        self.icon.show()

    def update_tooltip(self, status: str | None = None) -> None:
        if status is not None:
            self._status = status
        text = f"KeepT ({i18n.hotkey_label(self.app.config.hotkey)})"
        if self._status:
            text += f"\n{self._status}"
        self.icon.setToolTip(text)

    def notify(self, title: str, body: str, warning: bool = False) -> None:
        icon = QSystemTrayIcon.Warning if warning else QSystemTrayIcon.Information
        self.icon.showMessage(title, body, icon, 8000)

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.app.trigger()

    def rebuild(self) -> None:
        app, cfg = self.app, self.app.config
        m = self.menu
        m.clear()
        act = m.addAction(i18n.tr("tray_translate", hotkey=i18n.hotkey_label(cfg.hotkey)))
        act.triggered.connect(lambda: app.trigger())
        font = act.font()
        font.setBold(True)
        act.setFont(font)
        m.addSeparator()

        target_menu = m.addMenu(i18n.tr("tray_target"))
        group = QActionGroup(target_menu)
        sys_lang = app.system_lang
        options = [("", i18n.tr("tray_system_lang", lang=i18n.lang_name(cfg.effective_target(sys_lang))))]
        options += [(c, i18n.lang_name(c)) for c in ("de", "en", "es")]
        for code, label in options:
            a = target_menu.addAction(label)
            a.setCheckable(True)
            a.setChecked(cfg.target_lang == code)
            a.setActionGroup(group)
            a.triggered.connect(lambda checked=False, c=code: app.set_target(c))

        hk_menu = m.addMenu(i18n.tr("tray_hotkey"))
        hk_group = QActionGroup(hk_menu)
        presets = list(PRESETS)
        if cfg.hotkey not in presets:
            presets.insert(0, cfg.hotkey)
        for text in presets:
            a = hk_menu.addAction(i18n.hotkey_label(text))
            a.setCheckable(True)
            a.setChecked(text == cfg.hotkey)
            a.setActionGroup(hk_group)
            a.triggered.connect(lambda checked=False, t=text: app.set_hotkey(t))
        hk_menu.addSeparator()
        hk_menu.addAction(i18n.tr("tray_hotkey_custom")).triggered.connect(self._custom_hotkey)

        auto = m.addAction(i18n.tr("tray_autostart"))
        auto.setCheckable(True)
        auto.setChecked(cfg.autostart)
        auto.triggered.connect(lambda checked: app.set_autostart(checked))

        models_menu = m.addMenu(i18n.tr("tray_models"))
        installed = app.engine.translator.store.installed()
        if not installed:
            na = models_menu.addAction(i18n.tr("tray_models_none"))
            na.setEnabled(False)
        for info in installed:
            label = f"{i18n.lang_name(info.src)} → {i18n.lang_name(info.tgt)}  ({info.size_bytes / 1e6:.0f} MB)"
            sub = models_menu.addMenu(label)
            sub.addAction(i18n.tr("tray_models_delete")).triggered.connect(
                lambda checked=False, s=info.src, t=info.tgt: app.delete_model(s, t))
        models_menu.addSeparator()
        models_menu.addAction(i18n.tr("tray_models_open")).triggered.connect(self._open_models)

        m.addSeparator()
        m.addAction(i18n.tr("tray_quit")).triggered.connect(app.quit)

    def _custom_hotkey(self) -> None:
        dlg = HotkeyDialog()
        if dlg.exec() == QDialog.Accepted and dlg.result_text:
            self.app.set_hotkey(dlg.result_text)

    def _open_models(self) -> None:
        path = self.app.engine.translator.store.root
        path.mkdir(parents=True, exist_ok=True)
        services().open_folder(path)

    def hide(self) -> None:
        self.icon.hide()
