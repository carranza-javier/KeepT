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
from .ocr.pipeline import first_pass, reread_block
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
    blocks_read = Signal(int, object)  # session, ids of blocks read again by the line recognizer
    progress = Signal(int, str, float)  # session, kind ("download:<src>" / "loading"), fraction (-1 unknown)
    translated = Signal(int, int, str)  # session, block key, text
    translation_finished = Signal(int, float)  # session, seconds
    translation_failed = Signal(int, str, object)  # session, error kind, keys that failed
    preload_status = Signal(str, float)  # text for the tray tooltip, fraction (-1 = done)

    def __init__(self, translator: Translator | None = None, parent=None):
        super().__init__(parent)
        self.translator = translator or Translator()
        self._ocr_pool = ThreadPoolExecutor(1, thread_name_prefix="keept-ocr")
        self._tr_pool = ThreadPoolExecutor(1, thread_name_prefix="keept-translate")
        # Downloads get their own thread so a long model download never blocks translating
        # with the models that are already there.
        self._dl_pool = ThreadPoolExecutor(1, thread_name_prefix="keept-download")
        # Reloads after inactivity run on their own thread: a translation then waits only for
        # the model it needs (the translator's load lock), not for every model of the target.
        self._load_pool = ThreadPoolExecutor(1, thread_name_prefix="keept-load")
        self._active = 0
        self._lock = threading.Lock()
        # Second reading of the blocks of the current session: urgent ids (asked to translate)
        # go before the rest, which is read in reading order.
        self._reread_cond = threading.Condition()
        self._urgent: list[int] = []
        self._translating = 0  # translation calls queued or running

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
        ocr = ocr_backend()
        try:
            result = first_pass(ocr, bgra, hint_lang)
        except Exception as exc:  # noqa: BLE001 - shown as a human message
            log.exception("OCR failed")
            kind = "no_ocr" if "no OCR language" in str(exc) else "ocr"
            self.ocr_failed.emit(session, kind)
            return
        if not self._alive(session):
            return
        with self._reread_cond:
            self._urgent = []
        self.ocr_finished.emit(session, result)
        self._reread(session, result.blocks, bgra)

    def prioritize(self, session: int, block_ids) -> None:
        """Read these blocks again before the others (the user wants them translated)."""
        with self._reread_cond:
            if self._alive(session):
                self._urgent = [*block_ids, *(i for i in self._urgent if i not in block_ids)]
                self._reread_cond.notify()

    def _reread(self, session: int, blocks, bgra: np.ndarray) -> None:
        """Second reading of every block, on the OCR thread, until done or a new session."""
        from .ocr.recognizer import recognizer

        t0 = time.perf_counter()
        rec = recognizer()
        by_id = {b.id: b for b in blocks}
        rest = [b.id for b in blocks]
        done: set[int] = set()
        while self._alive(session) and len(done) < len(by_id):
            with self._reread_cond:
                urgent = [i for i in self._urgent if i not in done and i in by_id]
                self._urgent = urgent
                if not urgent and self._translating:
                    # Blocks nobody asked for yet wait while a translation runs: both need
                    # the CPU, and the translation is what the user is waiting for.
                    self._reread_cond.wait(0.1)
                    continue
            nxt = urgent[0] if urgent else next(i for i in rest if i not in done)
            try:
                reread_block(by_id[nxt], bgra, rec)
            except Exception:  # noqa: BLE001 - keep the Windows OCR reading of this block
                log.exception("Second reading of block %d failed", nxt)
                by_id[nxt].meta["confidence"] = 1.0
            done.add(nxt)
            if self._alive(session):
                self.blocks_read.emit(session, [nxt])
        log.info("Second reading of %d/%d block(s) in %.0f ms", len(done), len(by_id), (time.perf_counter() - t0) * 1000)

    def warm_up(self, lang: str) -> None:
        """Load WinRT and the OCR engine once, off the UI thread."""

        def run() -> None:
            t0 = time.perf_counter()
            try:
                ocr = ocr_backend()
                ocr.recognize(np.full((48, 160, 4), 255, np.uint8), lang)
            except Exception as exc:  # noqa: BLE001
                log.warning("OCR warm up failed: %s", exc)
            try:
                from .ocr.layout import Rect
                from .ocr.recognizer import recognizer

                rec = recognizer()
                if rec is not None:
                    rec.read(np.full((24, 120, 4), 255, np.uint8), [Rect(4, 4, 100, 16)])
            except Exception as exc:  # noqa: BLE001
                log.warning("Line recognizer warm up failed: %s", exc)
            try:
                from .translate import langdetect

                langdetect.warm_up()
            except Exception as exc:  # noqa: BLE001
                log.warning("Language detector warm up failed: %s", exc)
            log.info("OCR and language detection warm up %.0f ms", (time.perf_counter() - t0) * 1000)

        self._ocr_pool.submit(run)

    # -- translation -----------------------------------------------------------------
    def translate(self, session: int, jobs: list[TranslationJob], tgt: str,
                  names: frozenset[str] = frozenset()) -> None:
        with self._reread_cond:
            self._translating += 1
        self._tr_pool.submit(self._run_translate_counted, session, jobs, tgt, names)

    def _run_translate_counted(self, *args) -> None:
        try:
            self._run_translate(*args)
        finally:
            with self._reread_cond:
                self._translating -= 1
                self._reread_cond.notify()

    def _run_translate(self, session: int, jobs: list[TranslationJob], tgt: str,
                       names: frozenset[str] = frozenset()) -> None:
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
            # One block first so something appears quickly, then bigger chunks for throughput.
            i, size = 0, 1
            while i < len(group):
                if not self._alive(session):
                    return
                chunk = group[i:i + size]
                tc = time.perf_counter()
                try:
                    results = self.translator.translate([j.text for j in chunk], src, tgt, names=names)
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
        store = tr.store
        for n, pair in enumerate(pairs):
            if tr.is_pair_loaded(pair):
                continue
            if store.get(*pair) is None and store.download_progress(*pair) is not None:
                # Already being downloaded in the background: show that progress and wait.
                while store.get(*pair) is None and self._alive(session):
                    state = store.download_progress(*pair)
                    if state is None:
                        if store.get(*pair) is None:
                            raise ModelError("network", "background download failed")
                        break
                    done, total = state
                    self.progress.emit(session, f"download:{src}", (n + (done / total if total else 0.0)) / len(pairs))
                    time.sleep(0.25)
                if not self._alive(session):
                    return
            if store.get(*pair) is None:
                def progress(done: int, total: int, n=n) -> None:
                    frac = (done / total) if total else 0.0
                    self.progress.emit(session, f"download:{src}", (n + frac) / len(pairs))

                self.progress.emit(session, f"download:{src}", n / len(pairs))
                tr.model(pair, progress)
            else:
                # Models on disk load in about a second; the pending blocks already show the
                # shimmer, so no extra message is needed.
                tr.model(pair)

    # -- preload -------------------------------------------------------------------
    @staticmethod
    def _pairs_for(tgt: str, sources) -> list[tuple[str, str]]:
        """Models needed to translate the given source languages into `tgt` (most likely first)."""
        from .translate.setup_plan import needed_pairs

        return needed_pairs(tgt, sources)

    def preload(self, tgt: str, download: bool, sources=("en",)) -> None:
        """Load the models to translate `sources` into `tgt`; with `download`, fetch the
        missing ones first on the download thread (translations keep working meanwhile).
        Other languages are downloaded only when text in them is translated."""
        pairs = self._pairs_for(tgt, sources)
        self._tr_pool.submit(self._load_pairs, tgt, pairs)
        if download:
            missing = [p for p in pairs if self.translator.store.get(*p) is None]
            if missing:
                self._dl_pool.submit(self._download_pairs, tgt, missing)

    def _load_pairs(self, tgt: str, pairs) -> None:
        t0 = time.perf_counter()
        for pair in pairs:
            if self.translator.store.get(*pair) is None:
                continue
            try:
                self.translator.model(pair)
            except Exception as exc:  # noqa: BLE001 - preload is best effort
                log.warning("Preload of %s->%s failed: %s", *pair, exc)
        log.info("Preload for target %s done in %.1fs", tgt, time.perf_counter() - t0)

    def _download_pairs(self, tgt: str, pairs) -> None:
        store = self.translator.store
        for n, pair in enumerate(pairs):
            def progress(done: int, total: int, n=n) -> None:
                frac = (done / total) if total else 0.0
                self.preload_status.emit(f"{pair[0]}>{pair[1]}", (n + frac) / len(pairs))

            try:
                store.ensure(pair[0], pair[1], progress)
            except Exception as exc:  # noqa: BLE001 - retried on demand later
                log.warning("Background download of %s->%s failed: %s", *pair, exc)
        self.preload_status.emit("", -1.0)
        self._tr_pool.submit(self._load_pairs, tgt, pairs)

    # -- release after inactivity / reload on demand -----------------------------------
    def release_models(self) -> None:
        """Free the translation models (runs on the translation thread, so never mid job)."""
        self._tr_pool.submit(self._run_release)

    def _run_release(self) -> None:
        import gc

        n = self.translator.unload_all()
        gc.collect()
        log.info("Released %d model(s) after inactivity", n)

    def reload_models(self, tgt: str, sources) -> None:
        """Load the models for `sources` -> `tgt` again, in order (most likely first). A
        translation requested meanwhile waits only for the model it needs (with shimmer)."""
        pairs = self._pairs_for(tgt, sources)
        missing = [p for p in pairs if not self.translator.is_pair_loaded(p)
                   and self.translator.store.get(*p) is not None]
        if missing:
            self._load_pool.submit(self._run_reload, tgt, missing)

    def _run_reload(self, tgt: str, pairs) -> None:
        t0 = time.perf_counter()
        for pair in pairs:
            try:
                self.translator.model(pair)
            except Exception as exc:  # noqa: BLE001 - a translation will report it if needed
                log.warning("Reload of %s->%s failed: %s", *pair, exc)
        log.info("Reloaded %d model(s) for target %s in %.0f ms", len(pairs), tgt, (time.perf_counter() - t0) * 1000)

    def shutdown(self) -> None:
        self.set_active(-1)
        self.translator.unload_all()  # free CTranslate2 models now, not during interpreter teardown
        self._ocr_pool.shutdown(wait=False, cancel_futures=True)
        self._tr_pool.shutdown(wait=False, cancel_futures=True)
        self._dl_pool.shutdown(wait=False, cancel_futures=True)
        self._load_pool.shutdown(wait=False, cancel_futures=True)
        self._ocr_pool.shutdown(wait=True, cancel_futures=True)
        from .ocr import release as release_ocr

        release_ocr()
