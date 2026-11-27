"""Data that must come out of a translation exactly as it went in.

- E-mail addresses and URLs are never translated: they are always replaced by a marker
  before translating and put back afterwards.
- Numbers (dates, times, amounts) and place names usually survive a plain translation, and
  the plain translation reads better ("1 de diciembre de 2026" instead of "del X1 diciembre
  X2"). So they are translated as they are, and the result is checked: if a number or a name
  is missing or changed, the sentence is translated again with markers for them.
- Place names: Swiss municipalities (official list) and the word after a Swiss postal code
  ("3999 Musterwil"), plus street names before a house number ("Dorfstrasse 1"). Names are not
  guessed from capital letters: every German noun starts with one.

Markers look like "QX1": the models copy them unchanged (measured with every installed model;
"[1]" or "{1}" get dropped or translated more often).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PLACES_FILE = Path(__file__).with_name("swiss_places.txt")
SWISS_LANGS = {"de", "fr", "it"}

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.UNICODE)
_TLDS = "ch|li|de|at|fr|it|es|com|org|net|info|eu|io|uk|nl|be|pl|pt|admin\\.ch"
URL = re.compile(
    r"(?:https?://|www\.)[^\s<>\"']+[^\s<>\"'.,;:!?)\]]"
    r"|\b[\w-]+(?:\.[\w-]+)*\.(?:" + _TLDS + r")(?:/[^\s<>\"']*[^\s<>\"'.,;:!?)\]])?(?![\w@])",
    re.IGNORECASE)
# A number with its inner separators: "7.00", "11.30", "2'500.50", "1,5", "25".
NUMBER = re.compile(r"\d+(?:[.,:'’]\d+)*")
DIGITS = re.compile(r"\d+")
_MONTHS = (r"januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember|"
           r"janvier|février|mars|avril|juin|juillet|août|septembre|octobre|novembre|décembre|"
           r"gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|dicembre|"
           r"january|february|march|june|july|october|december")
_CAP = r"[A-ZÄÖÜÉÈÀÂÊÎÔÛÇ][\w’'-]*"
# "3999 Musterwil", "CH-8001 Zürich": an address part, so at the start of the text, after a
# separator or a house number, and the name ends the part ("1500 Meter hoch" is no address).
POSTCODE = re.compile(r"(?<![\w.'’])(?:CH-)?([1-9]\d{3})\s+([A-ZÄÖÜÉÈÀÂÊÎÔÛÇ][^\s;•·|()]*?)(?=,?(?:\s|$|[;•·|)]))")
_BEFORE_OK = re.compile(r"(?:^|[,;•·|(]|\d[a-z]?|\s[-–])\s*$")
_AFTER_OK = re.compile(r"^(?:\s*$|\s*[,;•·|)]|\s{2,}|\s+[-–]\s)")
_MONTH_BEFORE = re.compile(r"(?:" + _MONTHS + r")\s*$", re.IGNORECASE)
STREET = re.compile(r"\b[A-ZÄÖÜ][\wäöüß-]*(?:strasse|straße|gasse|weg|platz|allee|rain|ring|quai)(?=\s+\d+[a-z]?\b)")
MARKER = re.compile(r"Q\s?X\s?(\d{1,2})\b", re.IGNORECASE)


@lru_cache(maxsize=1)
def _places() -> re.Pattern | None:
    try:
        names = [n.strip() for n in PLACES_FILE.read_text(encoding="utf-8").splitlines()
                 if n.strip() and not n.startswith("#")]
    except OSError:
        return None
    names.sort(key=len, reverse=True)
    return re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(n) for n in names) + r")(?![\w-])")


def postcodes(text: str):
    """Matches of "<postal code> <Name>" that look like part of an address."""
    for m in POSTCODE.finditer(text):
        before = text[:m.start()]
        if (_BEFORE_OK.search(before) and not _MONTH_BEFORE.search(before)
                and _AFTER_OK.match(text[m.end():])):
            yield m


def screen_names(texts) -> frozenset[str]:
    """Names to keep on the whole screen: the words after a Swiss postal code. "3999 Musterwil"
    in the letter head also protects "Musterwil" in "Gemeindeverwaltung Musterwil"."""
    out = set()
    for text in texts:
        for m in postcodes(text):
            name = m.group(2).strip("’'-")
            if len(_letters(name)) >= 3:
                out.add(name)
    return frozenset(out)


def _letters(word: str) -> str:
    return "".join(c for c in word if c.isalpha()).lower()


_CAP_WORD = re.compile(r"(?<![\w-])[A-ZÄÖÜÉÈÀÂÊÎÔÛÇ][\w’'-]*")


def find_names(text: str, src: str, extra: frozenset[str] = frozenset()) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    if src in SWISS_LANGS:
        rx = _places()
        if rx is not None:
            spans += [m.span() for m in rx.finditer(text)]
        spans += [m.span(2) for m in postcodes(text)]
        spans += [m.span() for m in STREET.finditer(text)]
    if extra:
        # The same name elsewhere on the screen ("3999 Musterwil" in the header,
        # "Gemeindeverwaltung Musterwil" below).
        keys = {_letters(n) for n in extra}
        for m in _CAP_WORD.finditer(text):
            if _letters(m.group(0)) in keys:
                spans.append(m.span())
    return spans


def _merge(spans: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """Sorted spans without overlaps (the earlier, then longer one wins)."""
    out: list[tuple[int, int, str]] = []
    for a, b, kind in sorted(spans, key=lambda s: (s[0], -(s[1] - s[0]))):
        if out and a < out[-1][1]:
            continue
        out.append((a, b, kind))
    return out


@dataclass
class Protected:
    """A sentence split into plain text and protected spans."""

    text: str
    spans: list[tuple[int, int, str]]  # (start, end, kind) kind: "link" | "name" | "number"
    markers: dict[str, str] = field(default_factory=dict)

    def masked(self, level: int) -> str:
        """Text for the model. Level 0 masks links, 1 also names, 2 also numbers."""
        kinds = {"link"} | ({"name"} if level >= 1 else set()) | ({"number"} if level >= 2 else set())
        self.markers = {}
        out, pos = [], 0
        for a, b, kind in self.spans:
            out.append(self.text[pos:a])
            if kind in kinds:
                key = f"QX{len(self.markers) + 1}"
                self.markers[key] = self.text[a:b]
                out.append(key)
            else:
                out.append(self.text[a:b])
            pos = b
        out.append(self.text[pos:])
        return "".join(out)

    def restore(self, translated: str) -> str | None:
        """Put the markers back. None if one is missing (the model dropped it)."""
        seen = set()

        def put(m: re.Match) -> str:
            key = f"QX{int(m.group(1))}"
            if key not in self.markers:
                return m.group(0)
            seen.add(key)
            return self.markers[key]

        out = MARKER.sub(put, translated)
        return out if seen == set(self.markers) else None

    def has(self, kind: str) -> bool:
        return any(k == kind for _, _, k in self.spans)

    def max_level(self) -> int:
        kinds = {k for _, _, k in self.spans}
        return 2 if "number" in kinds else 1 if "name" in kinds else 0

    def check(self, translated: str) -> bool:
        """Every link and name is there unchanged and the numbers are the same."""
        if MARKER.search(translated):
            return False
        for a, b, kind in self.spans:
            if kind in ("link", "name") and self.text[a:b] not in translated:
                return False
        return Counter(DIGITS.findall(self.text)) == Counter(DIGITS.findall(translated))


def protect(text: str, src: str, names: frozenset[str] = frozenset()) -> Protected:
    spans = [(m.start(), m.end(), "link") for m in EMAIL.finditer(text)]
    spans += [(m.start(), m.end(), "link") for m in URL.finditer(text)]
    spans += [(a, b, "name") for a, b in find_names(text, src, names)]
    spans += [(m.start(), m.end(), "number") for m in NUMBER.finditer(text)]
    return Protected(text, _merge(spans))
