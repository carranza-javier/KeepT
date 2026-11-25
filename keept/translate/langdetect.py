"""Language detection for the supported languages.

py3langid (a maintained langid.py: naive Bayes over byte n-grams, BSD-3-Clause, 4.5 MB,
about 0.05 ms per text) restricted to KeepT's languages. Short texts such as button labels
are often ambiguous ("Cancelar" is Spanish and Portuguese), so the language of the rest of
the screen is used as a prior: it wins unless another language is clearly more likely.
"""

from __future__ import annotations

import threading
import unicodedata

from ..languages import CODES
from . import lexicon

# The prior (screen language) wins when its probability is at least this fraction of the best.
PRIOR_MARGIN = 0.3
# Short labels (a few words, often names) only leave the screen language with strong evidence:
# a wrong guess would download a model for a language that is not on the screen.
SHORT_WORDS = 3
SHORT_MIN_PROB = 0.9
# A short label stays untranslated if the target is at least this fraction as likely as the best.
TARGET_MARGIN = 0.3

_identifier = None
_lock = threading.Lock()


def _get():
    global _identifier
    if _identifier is None:
        with _lock:
            if _identifier is None:
                from py3langid.langid import MODEL_DIR, MODEL_FILE, LanguageIdentifier

                ident = LanguageIdentifier.from_modelpath(MODEL_DIR / MODEL_FILE, norm_probs=True)
                ident.set_languages(list(CODES))
                _identifier = ident
    return _identifier


def warm_up() -> None:
    """Load the model (about 0.1 s) off the UI thread before the first detection."""
    _get().classify("warm up")


def scores(text: str) -> dict[str, float]:
    """Normalised probability per supported language."""
    return dict(_get().rank(unicodedata.normalize("NFC", text)))


def detect(text: str, prior: str | None = None, target: str | None = None) -> tuple[str | None, float]:
    """Return (language, probability). With no letters at all, return the prior (or None).

    A short label made of known words is judged by its own words, whatever the rest of the
    screen is ("Restart now" is English on a German screen). If those words fit several
    languages ("Cancelar"), the screen language, then the target, then the detector decide.
    Other short texts (names, truncated labels) keep the screen language unless another one
    is clearly more likely."""
    if not any(c.isalpha() for c in text):
        return (prior if prior in CODES else None), 0.0
    probs = scores(text)
    by_words = lexicon.languages_of(text)
    if by_words:
        for pick in (prior, target):
            if pick in by_words:
                return pick, probs.get(pick, 0.0)
        best = max(by_words, key=lambda l: probs.get(l, 0.0))
        return best, probs.get(best, 0.0)
    best = max(probs, key=probs.get)
    if prior in probs and best != prior:
        short = len(text.split()) <= SHORT_WORDS
        if probs[prior] >= probs[best] * PRIOR_MARGIN or (short and probs[best] < SHORT_MIN_PROB):
            return prior, probs[prior]
    return best, probs[best]


def clearly(text: str, lang: str) -> bool:
    """True when the text is clearly in `lang`: its own words say so, or the detector is sure."""
    by_words = lexicon.languages_of(text)
    if by_words:
        return lang in by_words
    return scores(text).get(lang, 0.0) >= SHORT_MIN_PROB or len(text.split()) >= 8


def may_already_be(text: str, target: str) -> bool:
    """A short label that could already be in the target language is left as it is: leaving a
    doubtful label untranslated is better than breaking a correct one ("Guardar cambios" read
    as German comes back as "Guardar cambos")."""
    if not lexicon.is_short(text):
        return False
    by_words = lexicon.languages_of(text)
    if by_words:
        return target in by_words
    probs = scores(text)
    return probs.get(target, 0.0) >= TARGET_MARGIN * max(probs.values())
