"""Translation pipeline: sentence segmentation, batching, caching and pivoting through English."""

from __future__ import annotations

import logging
import re
import threading
import unicodedata
import time
from typing import Callable, Protocol

from ..languages import language_name_label
from . import protect
from .models import KNOWN_PAIRS, LoadedModel, ModelStore, Progress

log = logging.getLogger(__name__)

_ABBREV = {
    "z.b", "d.h", "u.a", "usw", "bzw", "ca", "dr", "nr", "str", "evtl", "ggf", "inkl", "max", "min",
    "e.g", "i.e", "etc", "vs", "mr", "mrs", "ms", "fig", "approx", "sr", "sra", "srta", "pág", "núm", "ej",
}
_SENT_END = re.compile(r"(?<=[.!?…:])\s+(?=[\"'“„«¿¡(\[]?[A-ZÄÖÜÁÉÍÓÚÑ0-9])")


def split_sentences(text: str) -> list[str]:
    # NFC: models are trained on composed characters; OCR or apps may hand us decomposed ones.
    text = unicodedata.normalize("NFC", " ".join(text.split()))
    if not text:
        return []
    parts: list[str] = []
    start = 0
    for m in _SENT_END.finditer(text):
        candidate = text[start:m.start()]
        last_word = candidate.rsplit(" ", 1)[-1].rstrip(".").lower()
        if candidate.endswith(".") and (last_word in _ABBREV or (len(last_word) == 1 and last_word.isalpha())):
            continue
        # German ordinals ("am 24. Dezember", "vom 3. bis 14. Juli") are not sentence ends.
        if candidate.endswith(".") and last_word.isdigit() and len(last_word) <= 2:
            continue
        parts.append(candidate)
        start = m.end()
    parts.append(text[start:])
    return [p for p in parts if p.strip()]


def route(src: str, tgt: str, pairs=KNOWN_PAIRS) -> list[tuple[str, str]]:
    """Model chain from src to tgt. Pivot through English when there is no direct model."""
    if src == tgt:
        return []
    if (src, tgt) in pairs:
        return [(src, tgt)]
    if (src, "en") in pairs and ("en", tgt) in pairs:
        return [(src, "en"), ("en", tgt)]
    raise ValueError(f"no translation route {src}->{tgt}")


_FINAL_MARKS = ".!?…"
_CLOSERS = "\"'”»)]"


def keep_final_mark(original: str, translated: str) -> str:
    """The models sometimes drop the final period of a sentence (the last sentence of a
    paragraph came back without it): give the translation the mark of the original."""
    src, out = original.rstrip(), translated.rstrip()
    if not src or not out or src[-1] not in _FINAL_MARKS:
        return translated
    if out.rstrip(_CLOSERS)[-1:] in _FINAL_MARKS + ":;":
        return translated
    return out + src[-1]


def match_case(original: str, translated: str) -> str:
    letters = [c for c in original if c.isalpha()]
    if len(letters) >= 2 and all(c.isupper() for c in letters):
        return translated.upper()
    return translated


class PairModel(Protocol):
    def translate(self, sentences: list[str]) -> list[str]: ...


class Translator:
    """Thread safe facade. Models are downloaded on demand, loaded once and kept in memory."""

    def __init__(self, store: ModelStore | None = None, loader: Callable[[str, str, Progress | None], PairModel] | None = None):
        self.store = store or ModelStore()
        # Two threads per model: measured as fast as six for one block, and the models of the
        # languages of a page run at the same time (see Engine), each with its own threads.
        from ..cpu import translation_threads

        self._threads = translation_threads()
        # Keep only an external loader here: storing the bound self._default_loader would create
        # a reference cycle that kept every CTranslate2 model alive until the interpreter shut
        # down, and freeing them that late crashed the process at exit.
        self._loader = loader
        self._models: dict[tuple[str, str], PairModel] = {}
        self._load_lock = threading.Lock()
        # One lock per model: CTranslate2 runs one batch at a time per model anyway, and
        # different models (German and French blocks of one page) run in parallel.
        self._run_locks: dict[tuple[str, str], threading.Lock] = {}
        self._locks_lock = threading.Lock()
        self._inflight: dict[tuple, threading.Event] = {}  # sentences being translated now
        self._cache: dict[tuple[str, str, str], str] = {}
        self._scache: dict[tuple, str] = {}  # (sentence, src, tgt, names in it) -> translation

    def _default_loader(self, src: str, tgt: str, progress: Progress | None) -> PairModel:
        info = self.store.ensure(src, tgt, progress)
        label = self.store.catalog.get((src, tgt), {}).get("target_label")
        return LoadedModel(info, self._threads, label)

    def is_pair_loaded(self, pair: tuple[str, str]) -> bool:
        return pair in self._models

    def is_loaded(self, src: str, tgt: str) -> bool:
        return all(p in self._models for p in route(src, tgt))

    def needs_download(self, src: str, tgt: str) -> bool:
        return any(p not in self._models and self.store.get(*p) is None for p in route(src, tgt))

    def model(self, pair: tuple[str, str], progress: Progress | None = None) -> PairModel:
        m = self._models.get(pair)
        if m is not None:
            return m
        if self._loader is None:
            # Download outside the load lock (the store has one lock per pair): a download of
            # one pair must never keep another pair that is already on disk from loading.
            self.store.ensure(pair[0], pair[1], progress)
        with self._load_lock:
            m = self._models.get(pair)
            if m is None:
                m = (self._loader or self._default_loader)(pair[0], pair[1], progress)
                self._models[pair] = m
        return m

    def unload(self, src: str, tgt: str) -> None:
        with self._load_lock:
            self._models.pop((src, tgt), None)
        self._cache.clear()
        self._scache.clear()

    def clear_cache(self) -> None:
        """Forget every translation (tools and benchmarks)."""
        self._cache.clear()
        self._scache.clear()

    def unload_all(self) -> int:
        """Drop every loaded model (memory is returned when the CTranslate2 objects go away).
        The translation cache is kept: it is small and makes repeated texts instant."""
        with self._load_lock:
            n = len(self._models)
            self._models.clear()
        return n

    def loaded_pairs(self) -> list[tuple[str, str]]:
        return list(self._models)

    def prepare(self, src: str, tgt: str, progress: Progress | None = None) -> None:
        """Download (if needed) and load every model on the route src -> tgt."""
        for pair in route(src, tgt):
            self.model(pair, progress)

    def translate(self, texts: list[str], src: str, tgt: str, progress: Progress | None = None,
                  names: frozenset[str] = frozenset()) -> list[str]:
        """Translate whole texts (blocks). Each text is split in sentences and all sentences go in
        one batch. `names` are extra names to keep unchanged (see protect.screen_names)."""
        if src == tgt:
            return list(texts)
        out: list[str | None] = [self._cache.get((t, src, tgt, names)) for t in texts]
        todo = [i for i, v in enumerate(out) if v is None]
        if todo:
            t0 = time.perf_counter()
            spans: list[tuple[int, int]] = []
            sentences: list[str] = []
            for i in todo:
                parts = split_sentences(texts[i])
                spans.append((len(sentences), len(sentences) + len(parts)))
                sentences.extend(parts)
            done = self._cached_sentences(sentences, src, tgt, progress, names)
            for i, (a, b) in zip(todo, spans):
                result = match_case(texts[i], unicodedata.normalize("NFC", " ".join(done[a:b]).strip()))
                self._cache[(texts[i], src, tgt, names)] = result
                out[i] = result
            log.debug("Translated %d texts %s->%s in %.0f ms", len(todo), src, tgt, (time.perf_counter() - t0) * 1000)
        return [o or "" for o in out]

    def sentences_cached(self, text: str, src: str, tgt: str, names: frozenset[str] = frozenset()) -> bool:
        return all(self._skey(s, src, tgt, names) in self._scache for s in split_sentences(text))

    @staticmethod
    def _skey(sentence: str, src: str, tgt: str, names: frozenset[str]):
        # Only the names in the sentence matter: a name found later elsewhere on the screen
        # does not make the sentences translated before it stale.
        return sentence, src, tgt, frozenset(n for n in names if n in sentence)

    def _cached_sentences(self, sentences: list[str], src: str, tgt: str, progress: Progress | None,
                          names: frozenset[str]) -> list[str]:
        """Translations of sentences, from the sentence cache when a previous call (often the
        translation in the background, one sentence at a time) already did them."""
        keys = [self._skey(s, src, tgt, names) for s in sentences]
        mine: list[int] = []
        theirs: list[threading.Event] = []
        with self._locks_lock:
            for i, k in enumerate(keys):
                if k in self._scache:
                    continue
                if k in self._inflight:
                    # Another thread (the background) is translating it right now: wait for it
                    # instead of doing the same work twice on a busy CPU.
                    theirs.append(self._inflight[k])
                elif all(keys[j] != k for j in mine):
                    self._inflight[k] = threading.Event()
                    mine.append(i)
        try:
            if mine:
                done = self._translate_sentences([sentences[i] for i in mine], src, tgt, progress, names)
                for i, text in zip(mine, done):
                    self._scache[keys[i]] = text
        finally:
            with self._locks_lock:
                for i in mine:
                    self._inflight.pop(keys[i]).set()
        for ev in theirs:
            ev.wait()
        missing = [i for i, k in enumerate(keys) if k not in self._scache]
        if missing:  # the other thread failed: translate them here
            done = self._translate_sentences([sentences[i] for i in missing], src, tgt, progress, names)
            for i, text in zip(missing, done):
                self._scache[keys[i]] = text
        return [self._scache[k] for k in keys]

    def _translate_sentences(self, sentences: list[str], src: str, tgt: str, progress: Progress | None,
                             names: frozenset[str]) -> list[str]:
        """Translate sentences keeping links, names and numbers exact. A sentence whose numbers
        or names do not survive is translated again with markers for them; if it still fails,
        it stays in the original language (a wrong date or amount is worse than none)."""
        items = [protect.protect(s, src, names) for s in sentences]
        results: list[str | None] = [language_name_label(s, src, tgt) for s in sentences]
        level = [0] * len(items)
        pending = [i for i, r in enumerate(results) if r is None]
        while pending:
            masked = [items[i].masked(level[i]) for i in pending]
            translated = self._run_route(masked, src, tgt, progress)
            retry = []
            for i, text in zip(pending, translated):
                item = items[i]
                restored = item.restore(text)
                if restored is not None and item.check(restored):
                    results[i] = keep_final_mark(sentences[i], restored)
                elif level[i] < item.max_level():
                    nxt = level[i] + 1
                    if nxt == 1 and not item.has("name"):
                        nxt = 2  # nothing to mask at level 1
                    # A level that masks nothing more would send the very same text again.
                    while nxt < item.max_level() and item.masked(nxt) == item.masked(level[i]):
                        nxt += 1
                    if item.masked(nxt) == item.masked(level[i]):
                        log.info("Kept a sentence untranslated: its numbers or names did not survive")
                        results[i] = item.text
                        continue
                    level[i] = nxt
                    retry.append(i)
                else:
                    log.info("Kept a sentence untranslated: its numbers or names did not survive")
                    results[i] = item.text
            pending = retry
        return [r or "" for r in results]

    def _run_route(self, texts: list[str], src: str, tgt: str, progress: Progress | None) -> list[str]:
        current = texts
        for pair in route(src, tgt):
            model = self.model(pair, progress)
            with self._locks_lock:
                lock = self._run_locks.setdefault(pair, threading.Lock())
            with lock:
                current = model.translate(current) if current else []
        return [c.strip() for c in current]
