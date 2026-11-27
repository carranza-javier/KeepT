"""Links, numbers and place names must come out of a translation exactly as they went in."""
import re

import pytest

from keept.translate import protect
from keept.translate.models import ModelStore
from keept.translate.translator import Translator


def spans(text, src="de", names=frozenset()):
    p = protect.protect(text, src, names)
    return [(text[a:b], kind) for a, b, kind in p.spans]


def test_links_are_found():
    found = spans("Schreiben Sie an gemeinde@musterwil.example oder besuchen Sie www.musterwil.ch und "
                  "https://example.org/a?b=1.")
    assert ("gemeinde@musterwil.example", "link") in found
    assert ("www.musterwil.ch", "link") in found
    assert ("https://example.org/a?b=1", "link") in found  # the final period is not part of it


def test_numbers_are_whole_expressions():
    found = spans("Ab dem 1. Dezember 2026 bis 7.00 Uhr, Gebühr 2'500.50 Franken.")
    assert [t for t, k in found if k == "number"] == ["1", "2026", "7.00", "2'500.50"]


def test_word_after_swiss_postcode_is_a_name_for_the_whole_screen():
    names = protect.screen_names(["Dorfstrasse 1 • 3999 Musterwil • gemeinde@musterwil.example",
                                  "Ab dem 1. Dezember 2026 wird", "über 1500 Meter hoch", "25. November 2026"])
    assert names == {"Musterwil"}
    assert ("Musterwil", "name") in spans("Gemeindeverwaltung Musterwil", names=names)


def test_postcode_rule_needs_an_address():
    assert protect.screen_names(["1500 Meter hoch", "im Dezember 2026 Bern", "CH-8001 Zürich, Schweiz"]) == {"Zürich"}


def test_swiss_municipalities_but_no_common_words():
    found = spans("Wir fahren nach Grindelwald und Aadorf, durch den Wald.")
    assert ("Grindelwald", "name") in found and ("Aadorf", "name") in found
    assert not any(t == "Wald" for t, _ in found)  # a municipality, but also an ordinary word


def test_street_before_house_number_is_a_name():
    assert ("Dorfstrasse", "name") in spans("Dorfstrasse 1")


def test_masking_and_restoring():
    p = protect.protect("Mail an info@x.ch ab 7.00 Uhr in Musterwil.", "de", frozenset({"Musterwil"}))
    assert p.masked(0) == "Mail an QX1 ab 7.00 Uhr in Musterwil."
    assert p.masked(1) == "Mail an QX1 ab 7.00 Uhr in QX2."
    assert p.masked(2) == "Mail an QX1 ab QX2 Uhr in QX3."
    assert p.restore("Correo a QX1 desde las QX2 en QX3.") == "Correo a info@x.ch desde las 7.00 en Musterwil."
    assert p.restore("Correo a Q X1 desde las qx2 en QX3.") == "Correo a info@x.ch desde las 7.00 en Musterwil."
    assert p.restore("Correo a QX1 desde las 7.") is None  # markers dropped


def test_check_numbers_and_names():
    p = protect.protect("Ab 7.00 Uhr in Musterwil.", "de", frozenset({"Musterwil"}))
    assert p.check("Desde las 7:00 en Musterwil.")  # same digits, other separator
    assert not p.check("Desde las 7 en Musterwil.")
    assert not p.check("Desde las 7:00 en Modeloswil.")


class MangleModel:
    """Like the real failures: translates names and e-mail parts, drops "00" of times."""

    def __init__(self, keep_markers=True):
        self.keep_markers = keep_markers
        self.calls = []

    def translate(self, sentences):
        self.calls.append(list(sentences))
        out = []
        for s in sentences:
            s = s.replace("Musterwil", "Modeloswil").replace("gemeinde", "munik").replace(".00", "")
            s = s.replace("Dal 1°", "A partir del 10")
            if not self.keep_markers:
                s = re.sub(r"QX\d+", "", s)
            out.append("ES:" + s)
        return out


def make(model):
    return Translator(ModelStore(), loader=lambda s, t, p: model)


def test_ladder_keeps_links_names_and_numbers_exact():
    model = MangleModel()
    tr = make(model)
    text = "Schreiben Sie an gemeinde@musterwil.example. Ab 7.00 Uhr in Musterwil."
    out = tr.translate([text], "it", "es", names=frozenset({"Musterwil"}))[0]
    assert "gemeinde@musterwil.example" in out and "7.00" in out and "Musterwil" in out
    assert "Modeloswil" not in out and "munik" not in out
    # the e-mail is masked from the start; numbers and names only after a failed check
    assert "QX1" in model.calls[0][0] and "7.00" in model.calls[0][1]


def test_sentence_stays_original_when_numbers_cannot_be_kept():
    tr = make(MangleModel(keep_markers=False))
    out = tr.translate(["Dal 1° dicembre alle 7.00. Grazie mille."], "it", "es")[0]
    assert "Dal 1° dicembre alle 7.00." in out  # never "10 de diciembre"
    assert "ES:Grazie mille." in out


def test_language_name_labels_use_the_table():
    tr = make(MangleModel())
    assert tr.translate(["DEUTSCH", "FRANÇAIS", "Italiano", "ENGLISH"], "de", "es") == \
        ["ALEMÁN", "FRANCÉS", "Italiano", "INGLÉS"]
    assert tr.translate(["FRANÇAIS"], "fr", "es") == ["FRANCÉS"]
    assert tr.translate(["Français:"], "it", "es") == ["Francés"]  # whatever language it was detected as
    assert tr.translate(["ENGLISH"], "en", "es") == ["INGLÉS"]
    assert tr.translate(["FRANGAIS"], "fr", "es") != ["FRANCÉS"]  # no guessing at misread names


@pytest.mark.parametrize("text", ["Hallo Welt.", "Keine Zahlen hier"])
def test_text_without_protected_data_is_translated_once(text):
    model = MangleModel()
    make(model).translate([text], "de", "es")
    assert len(model.calls) == 1


def test_screen_name_matches_whole_words_only():
    names = protect.screen_names(["Dorfstrasse 1 • 3999 Musterwil"])
    assert ("Musterwil", "name") in spans("Gemeindeverwaltung Musterwil", names=names)
    assert not any(k == "name" for _, k in spans("Die Muster sind da", names=names))
    assert not any(k == "name" for _, k in spans("Gemeindeverwaltung Mustervil", names=names))


def test_a_repeated_number_is_caught():
    # "from 8.00 to 11.30" must never come out as "de 8.00 a 11 11.30".
    p = protect.protect("The office is open from 8.00 to 11.30.", "en")
    assert p.check("La oficina abre de 8.00 a 11.30.")
    assert not p.check("La oficina abre de 8.00 a 11 11.30.")
    assert not p.check("La oficina abre de 8.00 a 11.")
