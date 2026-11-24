"""Entry point: tray, config, hotkey thread, overlay and model preloading."""

from __future__ import annotations

import argparse
import getpass
import logging
import sys
import time
from pathlib import Path

import numpy as np

from . import __version__, i18n
from .capture import Capture, ScreenGrabber
from .config import Config
from .platform import MonitorInfo, services

log = logging.getLogger("keept")


def load_image_bgra(path: str) -> np.ndarray:
    from PySide6.QtGui import QImage

    img = QImage(path).convertToFormat(QImage.Format_RGB32)
    if img.isNull():
        raise FileNotFoundError(path)
    arr = np.frombuffer(img.constBits(), np.uint8, img.sizeInBytes())
    return arr.reshape(img.height(), img.bytesPerLine() // 4, 4)[:, : img.width()].copy()


class KeepTApp:
    def __init__(self, qapp, args: argparse.Namespace):
        from PySide6.QtCore import QTimer

        from .engine import Engine
        from .hotkey import Hotkey, HotkeyService
        from .overlay.overlay_window import OverlayWindow
        from .tray import Tray

        self.qapp = qapp
        self.args = args
        self.config = Config.load()
        plat = services()
        self.system_lang = plat.system_language()
        i18n.set_ui_lang(self.system_lang)
        self.target = self.config.effective_target(self.system_lang)
        self.grabber = ScreenGrabber()
        self.fake_capture = load_image_bgra(args.fake_capture) if args.fake_capture else None

        self.engine = Engine()
        self.engine.preload_status.connect(self._on_preload_status)
        self.overlay = OverlayWindow(self.engine, self.target, plat.prefers_dark(),
                                     debug_blocks=args.debug_blocks or self.config.debug_blocks)
        self.overlay.hint_lang = self.config.last_source_lang
        self.overlay.closed.connect(self._on_overlay_closed)
        self.overlay.target_changed.connect(self._on_overlay_target)

        self.tray = Tray(self)

        self.hotkeys = HotkeyService(plat.hotkey_backend())
        self.hotkeys.activated.connect(self.trigger)
        self.hotkeys.status.connect(self._on_hotkey_status)
        try:
            hotkey = Hotkey.parse(self.config.hotkey)
        except ValueError:
            hotkey = Hotkey.parse("Ctrl+Alt+T")
            self.config.hotkey = str(hotkey)
        self.hotkeys.start(hotkey)

        self._warm_up()
        first_run = not self.config.first_run_done
        if first_run:
            if self.config.autostart:
                plat.set_autostart(True)
            self.tray.notify(i18n.tr("tray_ready_title"), i18n.tr("tray_ready_body", hotkey=self.config.hotkey))
            self.config.first_run_done = True
            self.config.save()
        QTimer.singleShot(1500, lambda: self.engine.preload(self.target, download=first_run))
        QTimer.singleShot(2500, self._check_ocr_languages)
        if args.open:
            QTimer.singleShot(300, self.trigger)

    # -- startup helpers -------------------------------------------------------------
    def _warm_up(self) -> None:
        """Pay one off initialisation costs now instead of on the first hotkey."""
        t0 = time.perf_counter()
        try:
            m = services().monitor_at_cursor()
            self.grabber.grab(MonitorInfo(m.device, m.left, m.top, 8, 8, m.scale))
        except Exception as exc:  # noqa: BLE001
            log.warning("Capture warm up failed: %s", exc)
        self.engine.warm_up(self.config.last_source_lang)
        try:
            self.overlay.warm_up()
        except Exception as exc:  # noqa: BLE001
            log.warning("Overlay warm up failed: %s", exc)
        log.info("Warm up done in %.0f ms", (time.perf_counter() - t0) * 1000)

    def _check_ocr_languages(self) -> None:
        if self.config.ocr_warning_shown:
            return
        try:
            from .ocr import backend

            available = backend().available_languages()
        except Exception as exc:  # noqa: BLE001
            log.error("Cannot query OCR languages: %s", exc)
            available = []
        missing = [c for c in ("de", "en", "es") if c not in available]
        log.info("OCR languages available: %s", available)
        if not missing:
            return
        tags = {"de": "de-DE", "en": "en-US", "es": "es-ES"}
        names = ", ".join(i18n.lang_name(c) for c in missing)
        self.tray.notify(i18n.tr("ocr_missing_title"), i18n.tr("ocr_missing_body", langs=names, tag=tags[missing[0]]),
                         warning=True)
        self.config.ocr_warning_shown = True
        self.config.save()

    # -- actions ---------------------------------------------------------------------
    def trigger(self, t_hotkey: float | None = None) -> None:
        if self.overlay.is_open():
            self.overlay.close_overlay()
            return
        t0 = t_hotkey or time.perf_counter()
        try:
            capture = self._capture()
        except Exception:  # noqa: BLE001
            log.exception("Capture failed")
            self.tray.notify("KeepT", i18n.tr("err_capture"), warning=True)
            return
        log.info("Captured %dx%d in %.0f ms", capture.width, capture.height, (time.perf_counter() - t0) * 1000)
        self.overlay.pill.set_theme(services().prefers_dark())
        self.overlay.open(capture, t0)

    def _capture(self) -> Capture:
        if self.fake_capture is not None:
            m = services().monitor_at_cursor()
            h, w = self.fake_capture.shape[:2]
            return Capture(MonitorInfo(m.device, m.left, m.top, w, h, m.scale), self.fake_capture)
        return self.grabber.grab_cursor_monitor()

    def set_target(self, code: str) -> None:
        self.config.target_lang = code
        self.config.save()
        self.target = self.config.effective_target(self.system_lang)
        self.overlay.target = self.target
        self.engine.preload(self.target, download=False)

    def _on_overlay_target(self, code: str) -> None:
        self.config.target_lang = code
        self.target = code
        self.config.save()

    def set_hotkey(self, text: str) -> None:
        from .hotkey import Hotkey

        try:
            hk = Hotkey.parse(text)
        except ValueError:
            return
        self.config.hotkey = str(hk)
        self.config.save()
        self.hotkeys.set_hotkey(hk)
        self.tray.update_tooltip()

    def set_autostart(self, enabled: bool) -> None:
        self.config.autostart = enabled
        self.config.save()
        services().set_autostart(enabled)

    def delete_model(self, src: str, tgt: str) -> None:
        self.engine.translator.unload(src, tgt)
        self.engine.translator.store.delete(src, tgt)

    def _on_hotkey_status(self, ok: bool, text: str) -> None:
        if not ok:
            self.tray.notify("KeepT", i18n.tr("hotkey_busy", hotkey=text), warning=True)

    def _on_preload_status(self, pair: str, fraction: float) -> None:
        if fraction < 0:
            self.tray.update_tooltip("")
        else:
            self.tray.update_tooltip(i18n.tr("downloading", pct=int(fraction * 100)))

    def _on_overlay_closed(self) -> None:
        if self.overlay.hint_lang != self.config.last_source_lang:
            self.config.last_source_lang = self.overlay.hint_lang
            self.config.save()

    def quit(self) -> None:
        self.overlay.close_overlay()
        self.hotkeys.stop()
        self.engine.shutdown()
        self.tray.hide()
        self.qapp.quit()


def _single_instance(qapp, on_message) -> bool:
    """Return False if another KeepT is already running (it is asked to open the overlay)."""
    from PySide6.QtNetwork import QLocalServer, QLocalSocket

    name = f"KeepT-{getpass.getuser()}"
    sock = QLocalSocket()
    sock.connectToServer(name)
    if sock.waitForConnected(150):
        sock.write(b"open")
        sock.flush()
        sock.waitForBytesWritten(300)
        return False
    QLocalServer.removeServer(name)
    server = QLocalServer(qapp)
    server.listen(name)

    def on_conn():
        conn = server.nextPendingConnection()
        conn.readyRead.connect(lambda: (conn.readAll(), on_message()))

    server.newConnection.connect(on_conn)
    qapp._keept_server = server  # keep alive
    return True


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="KeepT")
    ap.add_argument("--debug", action="store_true", help="verbose logging")
    ap.add_argument("--debug-blocks", action="store_true", help="draw detected OCR blocks")
    ap.add_argument("--fake-capture", metavar="PNG", help="use an image instead of the screen (testing)")
    ap.add_argument("--open", action="store_true", help="open the overlay right after start")
    ap.add_argument("--autostart", action="store_true", help=argparse.SUPPRESS)
    args, _ = ap.parse_known_args(argv)
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    services().init_process()
    from .paths import setup_logging

    log_file = setup_logging(args.debug)
    log.info("KeepT %s starting (Python %s), log at %s", __version__, sys.version.split()[0], log_file)

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    qapp = QApplication(sys.argv[:1])
    qapp.setApplicationName("KeepT")
    qapp.setQuitOnLastWindowClosed(False)

    holder: dict[str, KeepTApp] = {}
    if not _single_instance(qapp, lambda: holder["app"].trigger() if "app" in holder else None):
        log.info("KeepT already running, asked it to open the overlay")
        return 0
    from .icon import app_icon

    qapp.setWindowIcon(app_icon())
    holder["app"] = KeepTApp(qapp, args)
    return qapp.exec()


if __name__ == "__main__":
    raise SystemExit(main())
