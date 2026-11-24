"""Tiny language detector for German, English and Spanish (no dependencies).

Scores frequent function words, characteristic characters (ä ö ü ß ñ ¿ ¡ and
accented vowels) and typical word endings.
"""

from __future__ import annotations

import re

LANGS = ("de", "en", "es")

_WORDS = {
    "de": """der die das und ist nicht ein eine einen einem einer zu den dem des mit sie ich du wir ihr auf für von sich
        auch werden wird wurde sind hat haben bei oder wie nur noch aus nach über um kann können muss soll will
        diese dieser dieses alle mehr jetzt hier bitte zurück neu neue neuen ihre ihren sein seine keine kein
        nicht nichts schon sehr wenn dann aber also doch weil dass beim vom zum zur im ins am ob bis gegen
        ohne unter zwischen während immer wieder heute morgen gestern einstellungen datei speichern abbrechen
        öffnen schließen suchen hilfe weiter fertig anmelden abmelden konto passwort startseite übersetzen
        mich dich uns euch mein meine dein deine unser unsere euer eure jeder jede jedes man etwas viele
        gibt geht gut war waren hatte hatten wurden worden ja nein danke""",
    "en": """the and is are was were to of in that it for you with on this be not have has had your can will at by
        from or as an all more now here please back new they them their there what which who when where how
        would could should do does did done been being its our we my me he she his her him if then than but
        about into over after before just only also very some any no yes thank thanks settings file save
        cancel open close search help next done sign account password home translate update click download
        these those other such each every many much most get got make made use used using one two""",
    "es": """el la los las de que y en un una es por con para no se lo su sus al del más como pero le les ya o este
        esta estos estas son está están hay puede pueden todo toda todos nuevo nueva aquí ahora muy sin sobre
        entre también hasta desde cuando donde porque qué cómo cuál quién ser estar fue era han ha he hemos
        tu tus mi mis nuestro nuestra usted ustedes ellos ellas nosotros yo él ella me te nos os
        configuración archivo guardar cancelar abrir cerrar buscar ayuda siguiente listo iniciar sesión cuenta
        contraseña inicio traducir actualizar descargar haz clic aquí otra otro cada mucho muchos gracias sí""",
}

_WORDSETS = {lang: frozenset(words.split()) for lang, words in _WORDS.items()}
# Words that exist in more than one language count less.
_AMBIG = {w for w in set().union(*_WORDSETS.values()) if sum(w in s for s in _WORDSETS.values()) > 1}
_AMBIG |= {"a", "o", "es", "in", "an", "die", "den", "war", "son", "has", "hat", "man", "also", "will", "me", "no"}

_ENDINGS = {
    "de": ("ung", "ungen", "keit", "heit", "lich", "isch", "schaft", "chen", "lichen", "igen", "tz", "sch"),
    "en": ("ing", "tion", "tions", "ly", "ness", "ed", "ous", "ful", "ship", "able", "th"),
    "es": ("ción", "ciones", "dad", "dades", "mente", "ado", "ada", "ido", "ida", "aje", "ía", "ar", "ir"),
}

_TOKEN = re.compile(r"[A-Za-zÄÖÜäöüßÑñÁÉÍÓÚÜáéíóúü¿¡]+|[¿¡]")


def scores(text: str) -> dict[str, float]:
    s = {lang: 0.0 for lang in LANGS}
    if not text:
        return s
    lowered = text.lower()
    # Characters
    s["de"] += 2.0 * sum(lowered.count(c) for c in "äöüß")
    s["es"] += 2.5 * sum(lowered.count(c) for c in "ñ¿¡")
    s["es"] += 1.0 * sum(lowered.count(c) for c in "áéíóú")
    # German engine reads Spanish "ción" as "ciön": do not count that as German.
    fake = lowered.count("iön")
    s["de"] -= 2.0 * fake
    s["es"] += 2.0 * fake
    for token in _TOKEN.findall(text):
        w = token.lower()
        hits = [lang for lang in LANGS if w in _WORDSETS[lang]]
        if hits:
            weight = 0.6 if w in _AMBIG or len(hits) > 1 else 1.5
            for lang in hits:
                s[lang] += weight / len(hits)
        if len(w) >= 5:
            for lang in LANGS:
                if w.endswith(_ENDINGS[lang]):
                    s[lang] += 0.35
        # Capitalised words in the middle of a sentence are a German hint (nouns).
    caps_mid = re.findall(r"(?<=[a-zäöüß,]\s)[A-ZÄÖÜ][a-zäöüß]{3,}", text)
    s["de"] += 0.3 * len(caps_mid)
    return s


def detect(text: str, prior: str | None = None) -> tuple[str | None, float]:
    """Return (language, confidence 0..1). Language is None if there is no evidence.

    `prior` (for example the language of the rest of the screen) wins ties and
    weak evidence, which matters for short texts like button labels.
    """
    s = scores(text)
    if prior in s:
        s[prior] += 0.4
    ranked = sorted(s.items(), key=lambda kv: kv[1], reverse=True)
    (best, top), (_, second) = ranked[0], ranked[1]
    if top <= 0.4:
        return (prior if prior in s else None), 0.0
    confidence = (top - max(second, 0.0)) / top
    return best, max(0.0, min(1.0, confidence))
