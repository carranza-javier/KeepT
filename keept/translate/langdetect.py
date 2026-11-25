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

# The prior (screen language) wins when its probability is at least this fraction of the best.
PRIOR_MARGIN = 0.3

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


def detect(text: str, prior: str | None = None) -> tuple[str | None, float]:
    """Return (language, probability). With no letters at all, return the prior (or None)."""
    if not any(c.isalpha() for c in text):
        return (prior if prior in CODES else None), 0.0
    probs = scores(text)
    best = max(probs, key=probs.get)
    if prior in probs and best != prior and probs[prior] >= probs[best] * PRIOR_MARGIN:
        return prior, probs[prior]
    return best, probs[best]
