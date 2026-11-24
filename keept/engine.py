"""Background work: OCR and translation run on worker threads, results come back as Qt signals."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QObject, Signal

from .ocr import backend as ocr_backend
from .ocr.pipeline import read_screen
from .translate.models import ModelError
from .translate.translator import Translator, route

log = logging.getLogger(__name__)


@dataclass
class TranslationJob:
    key: int
    text: str
    src: str


class Engine(QObject):
    ocr_finished = Signal(int, object)  # session, ScreenText
    ocr_failed = Signal(int, str)  # session, error kind
    progress = Signal(int, str, float)  # session, kind ("download" / "loading"), fraction (-1 unknown)
    translated = Signal(int, int, str)  # session, block key, text
    translation_finished = Signal(int, float)  # session, seconds
    translation_failed = Signal(int, str, object)  # session, error kind, keys that failed
    preload_status = Signal(str, float)  # text for the tray tooltip, fraction (-1 = done)

    def __init__(self, translator: Translator | None = None, parent=None):
        super().__init__(parent)
        self.translator = translator or Translator()
        self._ocr_pool = ThreadPoolExecutor(1, thread_name_prefix="keept-ocr")
        self._tr_pool = ThreadPoolExecutor(1, thread_name_prefix="keept-translate")
        self._active = 0
        self._lock = threading.Lock()

    # -- sessions ------------------------------------------------------------------
    def set_active(self, session: int) -> None:
        with self._lock:
            self._active = session

    def _alive(self, session: int) -> bool:
        return self._active == session

    # -- OCR -----------------------------------------------------------------------
    def start_ocr(self, session: int, bgra: np.ndarray, hint_lang: str) -> None:
        self._ocr_pool.submit(self._run_ocr, session, bgra, hint_lang)

    def _run_ocr(self, session: int, bgra: np.ndarray, hint_lang: str) -> None:
        if not self._alive(session):
            return
        try:
            result = read_screen(ocr_backend(), bgra, hint_lang)
        except Exception as exc:  # noqa: BLE001 - shown as a human message
            log.exception("OCR failed")
            kind = "no_ocr" if "no OCR language" in str(exc) else "ocr"
            self.ocr_failed.emit(session, kind)
            return
        if self._alive(session):
            self.ocr_finished.emit(session, result)

    def warm_up(self, lang: str) -> None:
        """Load WinRT and the OCR engine once, off the UI thread."""

        def run() -> None:
            t0 = time.perf_counter()
            try:
                ocr = ocr_backend()
                langs = ocr.available_languages()
                # Every recognizer is used for re-reading blocks, so create them all now.
                for code in sorted(langs, key=lambda c: c != lang):
                    ocr.recognize(np.full((48, 160, 4), 255, np.uint8), code)
            except Exception as exc:  # noqa: BLE001
                log.warning("OCR warm up failed: %s", exc)
            log.info("OCR warm up %.0f ms", (time.perf_counter() - t0) * 1000)

        self._ocr_pool.submit(run)

    # -- translation -----------------------------------------------------------------
    def translate(self, session: int, jobs: list[TranslationJob], tgt: str) -> None:
        self._tr_pool.submit(self._run_translate, session, jobs, tgt)

    def _run_translate(self, session: int, jobs: list[TranslationJob], tgt: str) -> None:
        t0 = time.perf_counter()
        by_src: dict[str, list[TranslationJob]] = {}
        for job in jobs:
            by_src.setdefault(job.src, []).append(job)
        first_logged = False
        for src, group in by_src.items():
            if not self._alive(session):
                return
            try:
                self._prepare(session, src, tgt)
            except ModelError as exc:
                log.error("Model problem %s->%s: %s", src, tgt, exc)
                self.translation_failed.emit(session, exc.kind, [j.key for j in group])
                continue
            except Exception:  # noqa: BLE001
                log.exception("Could not load models %s->%s", src, tgt)
                self.translation_failed.emit(session, "translate", [j.key for j in group])
                continue
            # Small first chunk so something appears quickly, then bigger chunks for throughput.
            i, size = 0, 2
            while i < len(group):
                if not self._alive(session):
                    return
                chunk = group[i:i + size]
                tc = time.perf_counter()
                try:
                    results = self.translator.translate([j.text for j in chunk], src, tgt)
                except Exception:  # noqa: BLE001
                    log.exception("Translation failed")
                    self.translation_failed.emit(session, "translate", [j.key for j in chunk])
                    results = None
                if results is not None:
                    dt = time.perf_counter() - tc
                    for job, text in zip(chunk, results):
                        self.translated.emit(session, job.key, text)
                    log.info("Translated %d block(s) %s->%s in %.0f ms (%.0f ms/block)",
                             len(chunk), src, tgt, dt * 1000, dt * 1000 / len(chunk))
                    if not first_logged:
                        log.info("First translated block after %.0f ms", (time.perf_counter() - t0) * 1000)
                        first_logged = True
                i += size
                size = 6
        total = time.perf_counter() - t0
        log.info("Translation of %d block(s) finished in %.0f ms", len(jobs), total * 1000)
        self.translation_finished.emit(session, total)

    def _prepare(self, session: int, src: str, tgt: str) -> None:
        tr = self.translator
        if tr.is_loaded(src, tgt):
            return
        pairs = route(src, tgt)
        downloading = tr.needs_download(src, tgt)
        for n, pair in enumerate(pairs):
            if downloading:
                def progress(done: int, total: int, n=n) -> None:
                    frac = (done / total) if total else 0.0
                    self.progress.emit(session, "download", (n + frac) / len(pairs))

                self.progress.emit(session, "download", n / len(pairs))
                tr.model(pair, progress)
            else:
                self.progress.emit(session, "loading", -1.0)
                tr.model(pair)

    # -- preload -------------------------------------------------------------------
    def preload(self, tgt: str, download: bool) -> None:
        """Load (and on first run download) the models needed to translate into `tgt`."""
        self._tr_pool.submit(self._run_preload, tgt, download)

    def _run_preload(self, tgt: str, download: bool) -> None:
        t0 = time.perf_counter()
        sources = [s for s in ("de", "en", "es") if s != tgt]
        pairs: list[tuple[str, str]] = []
        for s in sources:
            for p in route(s, tgt):
                if p not in pairs:
                    pairs.append(p)
        store = self.translator.store
        for n, pair in enumerate(pairs):
            if store.get(*pair) is None and not download:
                continue
            try:
                def progress(done: int, total: int, n=n) -> None:
                    frac = (done / total) if total else 0.0
                    self.preload_status.emit(f"{pair[0]}>{pair[1]}", (n + frac) / len(pairs))

                self.translator.model(pair, progress)
            except Exception as exc:  # noqa: BLE001 - preload is best effort
                log.warning("Preload of %s->%s failed: %s", *pair, exc)
        self.preload_status.emit("", -1.0)
        log.info("Preload for target %s done in %.1fs", tgt, time.perf_counter() - t0)

    def shutdown(self) -> None:
        self.set_active(-1)
        self._ocr_pool.shutdown(wait=False, cancel_futures=True)
        self._tr_pool.shutdown(wait=False, cancel_futures=True)
