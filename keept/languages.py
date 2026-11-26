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


# Name of every supported language in every supported language. A label that is only a
# language name ("DEUTSCH", "Français") is translated with this table: the models turn an
# isolated language name into the name of the target language ("DEUTSCH" -> "ESPAÑOL").
NAMES_IN: dict[str, dict[str, str]] = {
    "de": dict(de="Deutsch", en="Englisch", es="Spanisch", fr="Französisch", it="Italienisch",
               pt="Portugiesisch", nl="Niederländisch", pl="Polnisch"),
    "en": dict(de="German", en="English", es="Spanish", fr="French", it="Italian", pt="Portuguese",
               nl="Dutch", pl="Polish"),
    "es": dict(de="alemán", en="inglés", es="español", fr="francés", it="italiano", pt="portugués",
               nl="neerlandés", pl="polaco"),
    "fr": dict(de="allemand", en="anglais", es="espagnol", fr="français", it="italien", pt="portugais",
               nl="néerlandais", pl="polonais"),
    "it": dict(de="tedesco", en="inglese", es="spagnolo", fr="francese", it="italiano", pt="portoghese",
               nl="olandese", pl="polacco"),
    "pt": dict(de="alemão", en="inglês", es="espanhol", fr="francês", it="italiano", pt="português",
               nl="neerlandês", pl="polaco"),
    "nl": dict(de="Duits", en="Engels", es="Spaans", fr="Frans", it="Italiaans", pt="Portugees",
               nl="Nederlands", pl="Pools"),
    "pl": dict(de="niemiecki", en="angielski", es="hiszpański", fr="francuski", it="włoski", pt="portugalski",
               nl="niderlandzki", pl="polski"),
}


def _plain(text: str) -> str:
    import unicodedata

    decomposed = unicodedata.normalize("NFD", text.strip().rstrip(":").strip())
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def language_name_label(text: str, src: str, tgt: str) -> str | None:
    """The label in `tgt` when `text` is just the name of a language written in `src`
    (accents may be missing, as OCR often drops them: "FRANCAIS")."""
    names = NAMES_IN.get(src)
    if not names or tgt not in NAMES_IN:
        return None
    key = _plain(text)
    for code, name in names.items():
        plain = _plain(name)
        # One character may be misread by the OCR in longer names ("FRANGAIS").
        if plain == key or (len(plain) >= 6 and len(key) == len(plain)
                            and sum(a != b for a, b in zip(plain, key)) == 1):
            out = NAMES_IN[tgt][code]
            letters = [c for c in text if c.isalpha()]
            if letters and all(c.isupper() for c in letters):
                return out.upper()
            if text.strip()[:1].isupper():
                return out[:1].upper() + out[1:]
            return out
    return None
