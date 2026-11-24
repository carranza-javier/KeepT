"""OCR: platform backend plus layout analysis."""

from __future__ import annotations

import sys
from typing import Protocol

import numpy as np

from .layout import Line


class OcrBackend(Protocol):
    def available_languages(self) -> list[str]:
        """Two letter codes of the installed recognizers, e.g. ["de", "en", "es"]."""

    def language_tags(self) -> dict[str, str]:
        """Map from two letter code to the full tag, e.g. {"de": "de-DE"}."""

    def recognize(self, bgra: np.ndarray, lang: str, scale: float = 1.0) -> list[Line]:
        """Run OCR on a BGRA image. Returned coordinates are in the input image pixels."""


_backend: OcrBackend | None = None


def backend() -> OcrBackend:
    global _backend
    if _backend is None:
        if sys.platform == "win32":
            from .windows_ocr import WindowsOcr

            _backend = WindowsOcr()
        else:  # pragma: no cover
            raise NotImplementedError("OCR backend only implemented for Windows in v1")
    return _backend
