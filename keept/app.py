"""Entry point: tray, config, hotkey thread, overlay and model preloading."""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np

from . import __version__, i18n
from .capture import Capture, ScreenGrabber
from .config import Config
from .platform import MonitorInfo, services

log = logging.getLogger("keept")

IDLE_RELEASE_MS = int(float(os.environ.get("KEEPT_IDLE_RELEASE_S", "600")) * 1000)  # env: tests only


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
        self._OverlayWindow = OverlayWindow
        self.overlays: dict = {}  # QScreen -> OverlayWindow (one per monitor, fixed DPI)
        for screen in qapp.screens():
            self._add_overlay(screen)
        self.overlay = self.overlays[qapp.primaryScreen()]
        qapp.screenAdded.connect(self._add_overlay)
        qapp.screenRemoved.connect(self._remove_overlay)

        self.hotkey_ok = True
        self._hotkey_previous: str | None = None
        self.tray = Tray(self)

        # Free the models after 10 minutes without using KeepT (one single shot timer, armed
        # only after the overlay closes); the hotkey reloads them in the background.
        self._idle_timer = QTimer()
        self._idle_timer.setSingleShot(True)
        self._idle_timer.setInterval(IDLE_RELEASE_MS)
        self._idle_timer.timeout.connect(self._release_if_idle)

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
            # The installer owns the initial "start with Windows" choice; afterwards the tray
            # toggle does. Here we only mirror the real state.
            self.config.autostart = plat.autostart_enabled()
            self.config.first_run_done = True
            self.config.save()
        self.prompt = None
        if not self.config.target_chosen:
            # Ask once which language to translate into; models are downloaded after the answer.
            QTimer.singleShot(600, self._ask_target)
        if self.config.target_chosen:  # on first run, wait for the answer
            QTimer.singleShot(1500, lambda: self.engine.preload(self.target, download=False))
            self._idle_timer.start()
        QTimer.singleShot(2500, self._check_ocr_languages)
        if args.open:
            QTimer.singleShot(300, self.trigger)

    # -- overlays per monitor ----------------------------------------------------------
    def _add_overlay(self, screen) -> None:
        if screen in self.overlays:
            return
        ov = self._OverlayWindow(self.engine, self.target, services().prefers_dark(),
                                 debug_blocks=self.args.debug_blocks or self.config.debug_blocks, screen=screen)
        ov.hint_lang = self.config.last_source_lang
        ov.closed.connect(lambda ov=ov: self._on_overlay_closed(ov))
        ov.target_changed.connect(self._on_overlay_target)
        self.overlays[screen] = ov

    def _remove_overlay(self, screen) -> None:
        ov = self.overlays.pop(screen, None)
        if ov is not None:
            ov.close_overlay()
            ov.deleteLater()
            if self.overlay is ov and self.overlays:
                self.overlay = next(iter(self.overlays.values()))

    def _open_overlay(self):
        return next((o for o in self.overlays.values() if o.is_open()), None)

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
            for ov in self.overlays.values():
                ov.warm_up()
        except Exception as exc:  # noqa: BLE001
            log.warning("Overlay warm up failed: %s", exc)
        log.info("Warm up done in %.0f ms", (time.perf_counter() - t0) * 1000)

    def _ask_target(self) -> None:
        from .onboarding import LanguagePrompt

        self.prompt = LanguagePrompt(services().prefers_dark(), self.target)
        self.prompt.chosen.connect(self._on_target_chosen)
        self.prompt.show_at_bottom()

    def _on_target_chosen(self, code: str) -> None:
        self.config.target_chosen = True
        self.config.target_lang = code
        self.config.save()
        self.target = code
        for ov in self.overlays.values():
            ov.target = code
        self.engine.preload(code, download=True)
        self.prompt.confirm(i18n.tr("onboard_done", hotkey=i18n.hotkey_label(self.config.hotkey)))
        log.info("First run: target language %s chosen", code)

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
        current = self._open_overlay()
        if current is not None:
            current.close_overlay()
            return
        t0 = t_hotkey or time.perf_counter()
        self._idle_timer.stop()
        # Start reloading released models right away, in parallel with capture and OCR.
        self.engine.reload_models(self.target, self.config.last_source_lang)
        try:
            capture = self._capture()
        except Exception:  # noqa: BLE001
            log.exception("Capture failed")
            self.tray.notify("KeepT", i18n.tr("err_capture"), warning=True)
            return
        log.info("Captured %dx%d in %.0f ms", capture.width, capture.height, (time.perf_counter() - t0) * 1000)
        screen = self._OverlayWindow._screen_for(capture.monitor)
        if screen is not None and screen not in self.overlays:
            self._add_overlay(screen)
        ov = self.overlays.get(screen, self.overlay)
        ov.pill.set_theme(services().prefers_dark())
        ov.target = self.target
        self.overlay = ov
        ov.open(capture, t0)

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
        for ov in self.overlays.values():
            ov.target = self.target
        self.engine.preload(self.target, download=False)

    def _on_overlay_target(self, code: str) -> None:
        self.config.target_lang = code
        self.target = code
        for ov in self.overlays.values():
            ov.target = code
        self.config.save()

    def set_hotkey(self, text: str) -> None:
        from .hotkey import Hotkey

        try:
            hk = Hotkey.parse(text)
        except ValueError:
            return
        old = self.config.hotkey
        if str(hk) == old and self.hotkey_ok:
            return
        # Check first, so a combination owned by another app never leaves KeepT without one.
        if not services().hotkey_available(hk):
            if self.hotkey_ok:
                msg = i18n.tr("hotkey_taken_kept", new=i18n.hotkey_label(str(hk)), old=i18n.hotkey_label(old))
            else:
                msg = i18n.tr("hotkey_busy", hotkey=i18n.hotkey_label(str(hk)))
            self.tray.notify("KeepT", msg, warning=True)
            log.info("Hotkey %s refused: taken by another app", hk)
            return
        self._hotkey_previous = old
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
        from .hotkey import Hotkey

        previous, self._hotkey_previous = self._hotkey_previous, None
        if ok:
            self.hotkey_ok = True
        elif previous and previous != text:
            # Lost a race with another app between the check and the registration: go back.
            self.tray.notify("KeepT", i18n.tr("hotkey_taken_kept", new=i18n.hotkey_label(text),
                                              old=i18n.hotkey_label(previous)), warning=True)
            self.config.hotkey = previous
            self.config.save()
            self.hotkeys.set_hotkey(Hotkey.parse(previous))
        else:
            self.hotkey_ok = False
            self.tray.notify("KeepT", i18n.tr("hotkey_busy", hotkey=i18n.hotkey_label(text)), warning=True)
        self.tray.update_tooltip()

    def _on_preload_status(self, pair: str, fraction: float) -> None:
        if fraction < 0:
            self.tray.update_tooltip("")
        else:
            self.tray.update_tooltip(i18n.tr("downloading", pct=int(fraction * 100)))

    def _release_if_idle(self) -> None:
        if self._open_overlay() is None:
            self.engine.release_models()

    def _on_overlay_closed(self, ov) -> None:
        self._idle_timer.start()
        for other in self.overlays.values():
            other.hint_lang = ov.hint_lang
        if ov.hint_lang != self.config.last_source_lang:
            self.config.last_source_lang = ov.hint_lang
            self.config.save()

    def quit(self) -> None:
        for ov in self.overlays.values():
            ov.close_overlay()
        self.hotkeys.stop()
        self.engine.shutdown()
        self.tray.hide()
        self.qapp.quit()


def selftest(image: str, target: str | None, out: str | None) -> int:
    """Headless check of the whole pipeline (OCR + language detection + translation) on an
    image or, with "screen", on the monitor under the cursor. Used to verify packaged builds."""
    import json

    from PySide6.QtGui import QGuiApplication

    from .ocr import backend
    from .ocr.pipeline import read_screen
    from .translate.translator import Translator

    app = QGuiApplication(sys.argv[:1])  # noqa: F841 - QImage needs it
    report: dict = {"python": sys.version.split()[0], "frozen": bool(getattr(sys, "frozen", False))}
    try:
        t0 = time.perf_counter()
        bgra = ScreenGrabber().grab_cursor_monitor().bgra if image == "screen" else load_image_bgra(image)
        report["ocr_languages"] = backend().available_languages()
        text = read_screen(backend(), bgra, "en")
        report["ocr_ms"] = round((time.perf_counter() - t0) * 1000)
        tgt = target or Config.load().effective_target(services().system_language())
        tr = Translator()
        blocks = [b for b in text.blocks if b.lang != tgt]
        t1 = time.perf_counter()
        for src in sorted({b.lang for b in blocks}):
            tr.prepare(src, tgt)
        report["model_load_ms"] = round((time.perf_counter() - t1) * 1000)
        t2 = time.perf_counter()
        results = []
        for b in blocks:
            tb = time.perf_counter()
            out_text = tr.translate([b.text], b.lang, tgt)[0]
            results.append({"src": b.lang, "text": b.text, "translation": out_text,
                            "ms": round((time.perf_counter() - tb) * 1000)})
        report["translate_ms_total"] = round((time.perf_counter() - t2) * 1000)
        report["target"] = tgt
        report["blocks"] = results
        report["ok"] = bool(results) and all(r["translation"] for r in results)
    except Exception as exc:  # noqa: BLE001
        log.exception("Selftest failed")
        report["ok"] = False
        report["error"] = repr(exc)
    data = json.dumps(report, ensure_ascii=False, indent=1)
    log.info("Selftest report: %s", data)
    if out:
        Path(out).write_text(data, encoding="utf-8")
    return 0 if report.get("ok") else 1


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
    ap.add_argument("--selftest", metavar="PNG|screen", help="run OCR and translation once and exit")
    ap.add_argument("--target", help="target language for --selftest")
    ap.add_argument("--selftest-out", metavar="JSON", help="write the --selftest report here")
    args, _ = ap.parse_known_args(argv)
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    services().init_process()
    from .paths import setup_logging

    log_file = setup_logging(args.debug)
    log.info("KeepT %s starting (Python %s), log at %s", __version__, sys.version.split()[0], log_file)

    if Config.load().low_memory:
        import os

        # Keep MKL but do not pre-pack weights: much less committed memory, ~20 % slower.
        # Must be set before ctranslate2 is first used.
        os.environ["CT2_PACKED_GEMM"] = "0"

    if args.selftest:
        return selftest(args.selftest, args.target, args.selftest_out)

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
