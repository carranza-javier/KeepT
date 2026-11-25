"""Supported languages: one place for codes, native names and Windows OCR packs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str  # ISO 639-1, used everywhere in KeepT
    iso3: str  # ISO 639-3, used by OPUS-MT
    native: str  # name in the language itself, shown in every language picker
    ocr_tag: str  # Windows OCR capability to install ("Language.OCR~~~<tag>~0.0.1.0")
    letters: str  # letters beyond a-z the language needs; a model must be able to write them


LANGUAGES: dict[str, Language] = {
    lang.code: lang
    for lang in (
        Language("de", "deu", "Deutsch", "de-DE", "äöüß"),
        Language("en", "eng", "English", "en-US", ""),
        Language("es", "spa", "Español", "es-ES", "áéíóúñü"),
        Language("fr", "fra", "Français", "fr-FR", "àâçéèêëîïôùûü"),
        Language("it", "ita", "Italiano", "it-IT", "àèéìòù"),
        Language("pt", "por", "Português", "pt-PT", "áâãàçéêíóôõú"),
        Language("nl", "nld", "Nederlands", "nl-NL", "éë"),
        Language("pl", "pol", "Polski", "pl-PL", "ąćęłńóśźż"),
    )
}
CODES = tuple(LANGUAGES)


def native_name(code: str) -> str:
    lang = LANGUAGES.get(code)
    return lang.native if lang else code
