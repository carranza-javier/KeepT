"""Translation pipeline: sentence segmentation, batching, caching and pivoting through English."""

from __future__ import annotations

import logging
import os
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
        self._threads = max(1, min(8, (os.cpu_count() or 4) // 2))
        # Keep only an external loader here: storing the bound self._default_loader would create
        # a reference cycle that kept every CTranslate2 model alive until the interpreter shut
        # down, and freeing them that late crashed the process at exit.
        self._loader = loader
        self._models: dict[tuple[str, str], PairModel] = {}
        self._load_lock = threading.Lock()
        self._run_lock = threading.Lock()
        self._cache: dict[tuple[str, str, str], str] = {}

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
            done = self._translate_sentences(sentences, src, tgt, progress, names)
            for i, (a, b) in zip(todo, spans):
                result = match_case(texts[i], unicodedata.normalize("NFC", " ".join(done[a:b]).strip()))
                self._cache[(texts[i], src, tgt, names)] = result
                out[i] = result
            log.debug("Translated %d texts %s->%s in %.0f ms", len(todo), src, tgt, (time.perf_counter() - t0) * 1000)
        return [o or "" for o in out]

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
                    results[i] = restored
                elif level[i] < item.max_level():
                    nxt = level[i] + 1
                    if nxt == 1 and not item.has("name"):
                        nxt = 2  # nothing to mask at level 1
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
            with self._run_lock:
                current = model.translate(current) if current else []
        return [c.strip() for c in current]
