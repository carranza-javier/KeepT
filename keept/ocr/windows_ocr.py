"""Wrapper around Windows.Media.Ocr (pywinrt)."""

from __future__ import annotations

import asyncio
import logging
import threading

import numpy as np

from .layout import Line, Rect, Word

log = logging.getLogger(__name__)


def _upscale(bgra: np.ndarray, factor: int) -> np.ndarray:
    """Bilinear-ish 2x upscale using Qt (thread safe for QImage)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage

    h, w = bgra.shape[:2]
    src = np.ascontiguousarray(bgra)
    img = QImage(src.data, w, h, w * 4, QImage.Format_RGB32)
    big = img.scaled(w * factor, h * factor, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    big = big.convertToFormat(QImage.Format_RGB32)
    arr = np.frombuffer(big.constBits(), np.uint8, big.sizeInBytes())
    return arr.reshape(big.height(), big.bytesPerLine() // 4, 4)[:, : big.width()].copy()


class WindowsOcr:
    def __init__(self) -> None:
        from winrt.windows.media.ocr import OcrEngine

        self._OcrEngine = OcrEngine
        self._engines: dict[str, object] = {}
        self._lock = threading.Lock()
        self._tags: dict[str, str] | None = None

    def language_tags(self) -> dict[str, str]:
        if self._tags is None:
            tags: dict[str, str] = {}
            for lang in self._OcrEngine.available_recognizer_languages:
                tag = lang.language_tag
                tags.setdefault(tag.split("-")[0].lower(), tag)
            self._tags = tags
        return self._tags

    def available_languages(self) -> list[str]:
        return list(self.language_tags())

    def _engine(self, lang: str):
        tags = self.language_tags()
        if not tags:
            raise RuntimeError("no OCR language installed")
        if lang not in tags:
            # Any Latin recognizer reads the other Latin languages reasonably well.
            lang = "en" if "en" in tags else next(iter(tags))
        with self._lock:
            eng = self._engines.get(lang)
            if eng is None:
                from winrt.windows.globalization import Language

                eng = self._OcrEngine.try_create_from_language(Language(tags[lang]))
                if eng is None:
                    raise RuntimeError(f"cannot create OCR engine for {lang}")
                self._engines[lang] = eng
        return eng

    def max_dimension(self) -> int:
        return int(self._OcrEngine.max_image_dimension)

    def recognize(self, bgra: np.ndarray, lang: str, scale: float = 1.0) -> list[Line]:
        from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap

        factor = int(scale) if scale >= 2 else 1
        img = _upscale(bgra, factor) if factor > 1 else np.ascontiguousarray(bgra)
        h, w = img.shape[:2]
        limit = self.max_dimension()
        if max(w, h) > limit:
            raise ValueError(f"image too large for OCR: {w}x{h}")
        engine = self._engine(lang)
        bitmap = SoftwareBitmap.create_copy_from_buffer(memoryview(img).cast("B"), BitmapPixelFormat.BGRA8, w, h)

        async def run():
            return await engine.recognize_async(bitmap)

        result = asyncio.run(run())
        inv = 1.0 / factor
        lines: list[Line] = []
        for line in result.lines:
            words = []
            for word in line.words:
                b = word.bounding_rect
                words.append(Word(word.text, Rect(b.x * inv, b.y * inv, b.width * inv, b.height * inv)))
            if words:
                lines.append(Line(words))
        return lines
