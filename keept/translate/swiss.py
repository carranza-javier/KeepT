"""Swiss Standard German to the German the translation models were trained on.

Texts written in Switzerland never use "ß" ("Strasse", "Grüsse") and have their own words
("Kehricht", "Velo", "parkieren", "Trottoir"). The OPUS-MT models learned German mostly from
Germany: "Strassenrand" comes out as "playa" and "Kehrichtabfuhr" as "Audiencia", while
"Straßenrand" and "Müllabfuhr" translate correctly. Before translating German, the Swiss
spelling and a short list of frequent Swiss words are rewritten to the usual German forms
(measured in tools/bench/swiss_german.py).
"""

from __future__ import annotations

import re
from typing import Callable

# Word parts where Swiss "ss" stands for "ß" (a long vowel or diphthong comes before it).
# Matched anywhere in a word, so compounds are covered ("Strassenrand", "Fussgänger").
_SZ_PARTS = (
    "strasse", "grüss", "gruss", "gross", "gröss", "fuss", "füss", "heiss", "schliess", "fliess",
    "giess", "geniess", "ausser", "äusser", "bloss", "massnahm", "massgeb", "massstab", "ausmass",
    "mässig", "gemäss", "spass", "weiss", "reiss", "beiss", "schweiss", "fleiss", "stoss", "süss",
    "strauss", "gefäss", "spiess", "abschliess", "verschliess",
)
# Whole words only: as parts of words they would also hit other words ("aussenden").
_SZ_WORDS = ("aussen", "draussen", "mass", "liess", "hiess", "stiess", "fliesst", "giesst")

_SZ_PART_RE = re.compile("|".join(sorted(_SZ_PARTS, key=len, reverse=True)), re.IGNORECASE)
_SZ_WORD_RE = re.compile(r"\b(?:" + "|".join(_SZ_WORDS) + r")\b", re.IGNORECASE)
_WORD_RE = re.compile(r"[A-Za-zÄÖÜäöüéèà]+")
_DIPHTHONG_SS = re.compile(r"(?:ei|ai|au|äu|eu|ie)ss", re.IGNORECASE)


def _sz(m: re.Match) -> str:
    return m.group(0).replace("ss", "ß")


# Swiss word -> word of Germany. (pattern, replacement); the replacement keeps the case of the
# first letter. Patterns are written for the lower case form unless they start a word.
_WORDS: list[tuple[str, str]] = [
    (r"kehricht", "müll"),  # Kehricht, Hauskehricht, Kehrichtabfuhr, Kehrichtsack
    (r"sperrgut", "sperrmüll"),
    (r"grüngut", "bioabfall"),
    (r"\bvelos\b", "fahrräder"),
    (r"\bvelo\b", "fahrrad"),
    (r"\bvelo(?=(?:fahr|weg|streifen|ständer|route|verleih|helm|tour|kurier|parkplatz|abstell|"
     r"garage|lampe|schloss|dieb|händler|laden|unfall)[a-zäöü]*\b)", "rad"),  # Velofahrer, Veloweg
    (r"(?<=[a-zäöü])velo\b", "rad"),  # Elektrovelo, Mietvelo
    (r"\bparkieren\b", "parken"),
    (r"\bparkiert\b", "geparkt"),
    (r"\bparkierte(?=[nmrs]?\b)", "geparkte"),
    (r"\bparkierung\b", "parken"),
    (r"\btrottoirs\b", "gehwege"),
    (r"\btrottoir\b", "gehweg"),
    (r"\bbillette\b", "fahrkarten"),
    (r"\bbillett\b", "fahrkarte"),
    (r"\bbillett(?=[a-zäöü])", "fahrkarten"),  # Billettautomat
    (r"\bspitäler\b", "krankenhäuser"),
    (r"\bspital(?=\b|[a-zäöü])", "krankenhaus"),
    (r"(?:(?<=kantons)|(?<=kinder))spital\b", "krankenhaus"),
    (r"\bnatel\b", "handy"),
    (r"\babwart(?=\b|in\b)", "hausmeister"),
    (r"\bhauswart(?=\b|in\b)", "hausmeister"),
    (r"\bgrillieren\b", "grillen"),
    (r"\bgrilliert\b", "gegrillt"),
    (r"\bvortritt\b", "vorrang"),
    (r"\bperron\b", "bahnsteig"),
    (r"\bcoiffeur\b", "friseur"),
    (r"\bcoiffeuse\b", "friseurin"),
    (r"\blavabo\b", "waschbecken"),
    (r"\bpoulet\b", "hähnchen"),
    (r"\brüebli\b", "karotten"),
    (r"\brahm\b", "sahne"),
    (r"\btraktandum\b", "tagesordnungspunkt"),
    (r"\btraktanden\b", "tagesordnungspunkte"),
    (r"\bpendenzen\b", "offene aufgaben"),
    (r"\ballfällig(?=(?:e[nmrs]?)?\b)", "eventuell"),
    (r"\binnert\b", "innerhalb"),
    (r"\bunterbruch\b", "unterbrechung"),
    (r"\bkondukteur\b", "schaffner"),
    (r"\bcamion\b", "lastwagen"),
    (r"\bzügeln\b", "umziehen"),
    (r"\bdetailhandel\b", "einzelhandel"),
]
_WORD_RES = [(re.compile(p, re.IGNORECASE), r) for p, r in _WORDS]


def _keep_case(original: str, replacement: str) -> str:
    if original.isupper() and len(original) > 1:
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _words(text: str) -> str:
    for rx, rep in _WORD_RES:
        text = rx.sub(lambda m, rep=rep: _keep_case(m.group(0), rep), text)
    return text


def _sharp_s(text: str, pieces: Callable[[str], int] | None) -> str:
    def word(m: re.Match) -> str:
        w = m.group(0)
        if "ss" not in w.lower() or w.isupper():
            return w  # all caps keeps "SS", as in Germany
        new = _SZ_PART_RE.sub(_sz, w)
        new = _SZ_WORD_RE.sub(_sz, new)
        if new == w and pieces is not None and _DIPHTHONG_SS.search(w):
            # Other words: "ß" if the model knows the "ß" spelling better (fewer pieces).
            candidate = _DIPHTHONG_SS.sub(lambda d: d.group(0)[:-2] + "ß", w)
            try:
                if pieces(candidate) < pieces(w):
                    new = candidate
            except Exception:  # noqa: BLE001 - spelling is only a hint
                pass
        return new

    return _WORD_RE.sub(word, text)


def normalize(text: str, pieces: Callable[[str], int] | None = None) -> str:
    """Rewrite Swiss spelling and vocabulary. `pieces(word)` (SentencePiece pieces of a word in
    the model's source vocabulary) decides "ss" or "ß" for words outside the built-in list."""
    return _sharp_s(_words(text), pieces)
