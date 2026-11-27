"""Background work: OCR and translation run on worker threads, results come back as Qt signals."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QObject, Signal

from .ocr import backend as ocr_backend
from .ocr.pipeline import block_confidence, first_pass, reread_line
from .translate.models import ModelError
from .translate.translator import Translator, route

log = logging.getLogger(__name__)

# Blocks of one language translated in one call at most (CTranslate2 batches their sentences).
MAX_BATCH = 8


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
        from .cpu import reread_helpers

        self._helpers = reread_helpers()
        self._reread_pool = ThreadPoolExecutor(max(1, self._helpers), thread_name_prefix="keept-reread")
        # Preloads and releases of models run here, one at a time.
        self._tr_pool = ThreadPoolExecutor(1, thread_name_prefix="keept-translate")
        # Translations get one thread per source language: each language has its own model,
        # so a page in German, French and Italian translates the three at the same time,
        # while the blocks of one language keep their reading order.
        self._lang_pools: dict[str, ThreadPoolExecutor] = {}
        from .cpu import translation_slots

        self._tr_slots = threading.Semaphore(translation_slots())
        self._queues: dict[str, deque] = {}  # source language -> (session, tgt, names, job)
        self._draining: set[str] = set()  # languages whose thread is working on its queue
        self._first_done = -1  # last session that already has a translated block
        # Translation in the background (see speculate): one thread, one sentence at a time.
        self._bg: deque = deque()  # (session, tgt, names, job)
        self._bg_running = False
        self._bg_pool = ThreadPoolExecutor(1, thread_name_prefix="keept-background")
        self._urgent_reading = 0  # blocks the user asked for being read right now
        self._taken: set[int] = set()  # blocks of the current session read or being read
        self._reading = False  # second reading of a screen in progress
        self._asked_many = False  # several blocks asked for at once in this session
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
            self._taken = set()
            self._asked_many = False
        self.ocr_finished.emit(session, result)
        self._reread(session, result.blocks, bgra)

    def prioritize(self, session: int, block_ids) -> None:
        """Read these blocks again before the others (the user wants them translated)."""
        with self._reread_cond:
            if self._alive(session):
                # Blocks already read (or being read) are not waited for.
                if len(block_ids) >= 2:
                    self._asked_many = True
                block_ids = [i for i in block_ids if i not in self._taken]
                self._urgent = [*block_ids, *(i for i in self._urgent if i not in block_ids)]
                self._reread_cond.notify_all()

    def _reread(self, session: int, blocks, bgra: np.ndarray) -> None:
        """Second reading of every line until done or a new session, one line at a time so the
        user never waits for more than one line nobody asked for. The OCR thread reads the
        screen in reading order; lines of blocks the user asks for go first, and a few more
        threads read them too (the recognizer is thread safe): the lines of one paragraph at
        the same time, and with several blocks asked for (Enter) the longest first, since
        its translation takes longest too."""
        from .ocr.recognizer import recognizer

        t0 = time.perf_counter()
        rec = recognizer()
        by_id = {b.id: b for b in blocks}
        rest = [b.id for b in blocks]
        todo = {b.id: list(range(len(b.lines))) for b in blocks}  # lines nobody took yet
        left = {b.id: len(b.lines) for b in blocks}  # lines not read yet
        results: dict[int, list] = {b.id: [None] * len(b.lines) for b in blocks}
        taken: set[int] = {b.id for b in blocks if not b.lines}  # blocks with every line taken
        with self._reread_cond:
            self._taken = taken
        done: list[int] = []

        def remaining(bid: int) -> float:
            return sum(by_id[bid].lines[i].rect.w for i in todo[bid])

        def pop(bid: int) -> int:
            i = todo[bid].pop(0)
            if not todo[bid]:
                taken.add(bid)
            return i

        def take(helper: bool) -> tuple[int, int, bool] | None:
            with self._reread_cond:
                while self._alive(session) and len(taken) < len(by_id):
                    urgent = [i for i in self._urgent if todo.get(i)]
                    self._urgent = urgent
                    # Helpers join only after several blocks were asked for (Enter, a selection): their
                    # one thread sessions are slower per line, so for one block (a click) the
                    # main thread alone is faster (measured: 123 ms vs 400-500 ms per line).
                    if urgent and (not helper or self._asked_many):
                        bid = max(urgent, key=remaining) if helper else urgent[0]
                        self._urgent_reading += 1
                        return bid, pop(bid), True
                    if helper or self._translating or self._urgent_reading:
                        # Lines nobody asked for yet wait while the user waits for something
                        # (a line being read for them, a translation): both need the CPU.
                        self._reread_cond.wait(0.1)
                        continue
                    bid = next(i for i in rest if todo[i])
                    return bid, pop(bid), False
                return None

        def work(helper: bool = False) -> None:
            reader = recognizer(single_thread=True) if helper else rec
            while (item := take(helper)) is not None:
                bid, index, asked = item
                try:
                    res = reread_line(by_id[bid], index, bgra, reader)
                except Exception:  # noqa: BLE001 - keep the Windows OCR reading of this line
                    log.exception("Second reading of a line of block %d failed", bid)
                    res = (1.0, 1)
                with self._reread_cond:
                    results[bid][index] = res
                    left[bid] -= 1
                    finished = left[bid] == 0
                    if asked:
                        self._urgent_reading -= 1
                        self._reread_cond.notify_all()
                if finished:
                    by_id[bid].meta["confidence"] = block_confidence(results[bid])
                    done.append(bid)
                    if self._alive(session):
                        self.blocks_read.emit(session, [bid])

        for b in blocks:
            if not b.lines:
                b.meta["confidence"] = 0.0
        with self._reread_cond:
            self._reading = True
        try:
            helpers = [self._reread_pool.submit(work, True) for _ in range(self._helpers)]
            work()
            for f in helpers:
                f.result()
        finally:
            with self._reread_cond:
                self._reading = False
                self._reread_cond.notify_all()
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

                for single in (False, True):
                    rec = recognizer(single_thread=single)
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
        """Queue blocks for translation. Each source language has its own queue and thread."""
        start: list[str] = []
        with self._reread_cond:
            # Blocks asked for leave the background queue: the foreground does them now.
            keys = {(session, j.key) for j in jobs}
            if self._bg:
                self._bg = deque(e for e in self._bg if (e[0], e[3].key) not in keys)
            for job in jobs:
                queue = self._queues.setdefault(job.src, deque())
                queue.append((session, tgt, names, job))
                self._translating += 1
                if job.src not in self._draining:
                    self._draining.add(job.src)
                    start.append(job.src)
            for src in start:
                pool = self._lang_pools.get(src)
                if pool is None:
                    pool = self._lang_pools[src] = ThreadPoolExecutor(1, thread_name_prefix=f"keept-translate-{src}")
                pool.submit(self._drain, src)

    # -- translation in the background ---------------------------------------------------
    def speculate(self, session: int, jobs: list[TranslationJob], tgt: str,
                  names: frozenset[str] = frozenset()) -> None:
        """Translate blocks nobody asked for yet, in the background, so "Translate screen"
        finds them done. Only with models that are already on disk (never a download), one
        sentence at a time, and only while the user waits for nothing: a block asked for
        (being read or translated) pauses it after the current sentence."""
        with self._reread_cond:
            self._bg.extend((session, tgt, names, job) for job in jobs)
            if self._bg_running:
                return
            self._bg_running = True
        self._bg_pool.submit(self._run_background)

    def _foreground_busy(self) -> bool:
        # The second reading of the screen goes first too: a click or Enter needs it, and the
        # background would slow it down.
        return bool(self._translating or self._urgent or self._urgent_reading or self._reading)

    def _next_sentence(self):
        """Wait until the foreground is idle, then hand out the next block of the background
        queue. None when the queue is empty (the thread ends)."""
        with self._reread_cond:
            while True:
                while self._bg and not self._alive(self._bg[0][0]):
                    self._bg.popleft()
                if not self._bg:
                    self._bg_running = False
                    return None
                if not self._foreground_busy():
                    return self._bg[0]
                self._reread_cond.wait(0.2)

    def _run_background(self) -> None:
        from .translate.translator import split_sentences

        t0, n = time.perf_counter(), 0
        while (head := self._next_sentence()) is not None:
            session, tgt, names, job = head
            tr = self.translator
            todo = []
            try:
                if not tr.needs_download(job.src, tgt):
                    todo = [s for s in split_sentences(job.text)
                            if not tr.sentences_cached(s, job.src, tgt, names)]
            except Exception:  # noqa: BLE001 - background work is best effort
                todo = []
            if todo:
                # One sentence per call: the foreground waits for at most one sentence.
                try:
                    tr.translate([todo[0]], job.src, tgt, names=names)
                    n += 1
                except Exception:  # noqa: BLE001 - the foreground will report it if it matters
                    log.exception("Background translation failed")
                    todo = []
            if len(todo) <= 1:
                with self._reread_cond:
                    if self._bg and self._bg[0] is head:
                        self._bg.popleft()
        if n:
            log.info("Background: %d sentence(s) translated in %.0f ms", n, (time.perf_counter() - t0) * 1000)

    def wait_translations(self, timeout: float = 10.0) -> bool:
        """Wait until no translation is queued or running (tests and tools)."""
        end = time.perf_counter() + timeout
        with self._reread_cond:
            while self._translating:
                left = end - time.perf_counter()
                if left <= 0:
                    return False
                self._reread_cond.wait(left)
        return True

    def _next_batch(self, src: str):
        """The queued jobs of `src` that can go in one batch: same session, target and names,
        at most MAX_BATCH; only one for the first translation of a session (it shows up sooner).
        Jobs of an old session are dropped. None when the queue is empty."""
        with self._reread_cond:
            queue = self._queues[src]
            while queue and not self._alive(queue[0][0]):
                queue.popleft()
                self._translating -= 1
            if not queue:
                self._draining.discard(src)
                self._reread_cond.notify_all()
                return None
            session, tgt, names, _ = queue[0]
            limit = 1 if self._first_done != session else MAX_BATCH
            batch: list[TranslationJob] = []
            while queue and len(batch) < limit and queue[0][:3] == (session, tgt, names):
                batch.append(queue.popleft()[3])
            self._reread_cond.notify_all()
            return session, tgt, names, batch

    def _drain(self, src: str) -> None:
        """Translation thread of one source language: blocks that became ready while the
        previous batch ran go together in the next one (a batch costs much less than one call
        per block), in reading order."""
        while (nxt := self._next_batch(src)) is not None:
            session, tgt, names, batch = nxt
            try:
                self._run_translate(session, batch, tgt, names)
            finally:
                with self._reread_cond:
                    self._translating -= len(batch)
                    self._reread_cond.notify_all()

    def _run_translate(self, session: int, jobs: list[TranslationJob], tgt: str,
                       names: frozenset[str] = frozenset()) -> None:
        """Translate jobs of one source language in one batch."""
        if not self._alive(session):
            return
        src = jobs[0].src
        t0 = time.perf_counter()
        try:
            self._prepare(session, src, tgt)
        except ModelError as exc:
            log.error("Model problem %s->%s: %s", src, tgt, exc)
            self.translation_failed.emit(session, exc.kind, [j.key for j in jobs])
            return
        except Exception:  # noqa: BLE001
            log.exception("Could not load models %s->%s", src, tgt)
            self.translation_failed.emit(session, "translate", [j.key for j in jobs])
            return
        if not self._alive(session):
            return
        tc = time.perf_counter()
        try:
            with self._tr_slots:
                results = self.translator.translate([j.text for j in jobs], src, tgt, names=names)
        except Exception:  # noqa: BLE001
            log.exception("Translation failed")
            self.translation_failed.emit(session, "translate", [j.key for j in jobs])
            return
        dt = time.perf_counter() - tc
        for job, text in zip(jobs, results):
            self.translated.emit(session, job.key, text)
        with self._reread_cond:
            first = self._first_done != session
            self._first_done = session
        log.info("Translated %d block(s) %s->%s in %.0f ms (%.0f ms/block)%s",
                 len(jobs), src, tgt, dt * 1000, dt * 1000 / len(jobs), " (first of the session)" if first else "")
        self.translation_finished.emit(session, time.perf_counter() - t0)

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
        for pool in list(self._lang_pools.values()):
            pool.shutdown(wait=False, cancel_futures=True)
        self._reread_pool.shutdown(wait=False, cancel_futures=True)
        self._bg_pool.shutdown(wait=False, cancel_futures=True)
        self._dl_pool.shutdown(wait=False, cancel_futures=True)
        self._load_pool.shutdown(wait=False, cancel_futures=True)
        self._ocr_pool.shutdown(wait=True, cancel_futures=True)
        from .ocr import release as release_ocr

        release_ocr()
