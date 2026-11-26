"""The Musterwil sample letter (docs/Musterwil_Kehrichtabfuhr.docx): German, French, Italian and
English on one page, with an e-mail address, dates, times and a place name.

tests/data/letter_100.png and letter_150.png are the letter as a word processor shows it at
100 % and 150 % (tools/render_letter.py). The OCR tests need Windows OCR, the translation tests
the installed models; they are skipped where these are missing.
"""
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from keept.ocr.layout import Rect
from keept.overlay.selection import Gesture, select_blocks
from keept.translate import protect

DATA = Path(__file__).with_name("data")
EMAIL = "gemeinde@musterwil.example"


def load(name):
    from PySide6.QtGui import QImage

    img = QImage(str(DATA / name)).convertToFormat(QImage.Format_RGB32)
    arr = np.frombuffer(img.constBits(), np.uint8, img.sizeInBytes())
    return arr.reshape(img.height(), img.bytesPerLine() // 4, 4)[:, : img.width()].copy()


def ocr_or_skip():
    if sys.platform != "win32":
        pytest.skip("Windows OCR only")
    from keept.ocr import backend

    try:
        ocr = backend()
        langs = ocr.available_languages()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no Windows OCR: {exc}")
    if not langs:
        pytest.skip("no OCR language installed")
    return ocr


@pytest.fixture(scope="module", params=["letter_100.png", "letter_150.png"])
def screen(request):
    from keept.ocr.pipeline import read_screen

    ocr = ocr_or_skip()
    return read_screen(ocr, load(request.param), "de"), request.param


def block(st, start):
    return next(b for b in st.blocks if b.text.startswith(start))


def test_no_underscores_and_exact_numbers(screen):
    st, _ = screen
    text = " ".join(b.text for b in st.blocks)
    assert "_" not in text
    assert "Ab dem 1. Dezember 2026" in text
    assert "Dal 1° dicembre 2026" in text  # not "10 dicembre"
    assert "7.00 Uhr" in text and "entro le ore 7.00." in text
    assert "from 8.00 to 11.30." in text
    assert "25. November 2026" in text


def test_email_is_read_exactly(screen):
    st, name = screen
    if name == "letter_100.png":
        pytest.skip("9 pt grey text at 100 %: Windows OCR misreads letters of the address itself")
    assert any(b.text == EMAIL for b in st.blocks)


def test_labels_paragraphs_and_footer_are_separate_blocks(screen):
    st, _ = screen
    texts = [b.text for b in st.blocks]
    for label in ("DEUTSCH", "FRAN", "ITALIANO", "ENGLISH"):
        # never glued to the paragraph below (the OCR reads Ç as C or G)
        assert any(t.startswith(label) and len(t) <= 8 for t in texts), label
    for item in ("Freundliche Grüsse", "Meilleures salutations", "Cordiali saluti",
                 "Fiktives Beispieldokument", "Fictitious sample document"):
        assert item in texts
    assert block(st, "Questions?").text.endswith("on our website.")  # not glued to the Italian


def test_every_block_has_its_own_language(screen):
    st, _ = screen
    expected = {"Ab dem": "de", "Dal 1°": "it", "Questions?": "en", "Freundliche": "de", "Meilleures": "fr",
                "Cordiali": "it", "Fiktives": "de", "Fictitious": "en", "Collecte": "fr", "Raccolta": "it"}
    for start, lang in expected.items():
        assert block(st, start).lang == lang, start
    french = next(b for b in st.blocks if "partir du 1er" in b.text)
    assert french.lang == "fr"


def test_rectangle_over_three_languages_keeps_each_language(screen):
    st, _ = screen
    fr = next(b for b in st.blocks if "partir du 1er" in b.text)
    en = block(st, "Questions?")
    # from the middle of the French paragraph to the middle of the English one
    r = Rect(fr.rect.x + 40, fr.lines[1].rect.cy, en.rect.w * 0.6, en.lines[0].rect.cy - fr.lines[1].rect.cy)
    chosen = select_blocks(st.blocks, Gesture("rect", ((r.x, r.y), (r.right, r.bottom)), r))
    langs = {b.text.split()[0]: b.lang for b in chosen}
    assert set(langs.values()) == {"fr", "it", "en"}
    assert fr in chosen and len(next(b for b in chosen if b is fr).lines) == len(fr.lines)  # whole block


def models_or_skip(*pairs):
    from keept.translate.models import ModelStore

    store = ModelStore()
    missing = [p for p in pairs if store.get(*p) is None]
    if missing:
        pytest.skip(f"models not installed: {missing}")


@pytest.fixture(scope="module")
def translator():
    from keept.translate.translator import Translator

    models_or_skip(("de", "es"), ("fr", "es"), ("it", "es"), ("en", "es"))
    return Translator()


LETTER = {
    "de": ["Gemeinde Musterwil", "Dorfstrasse 1", "3999 Musterwil", EMAIL, "Musterwil, 25. November 2026",
           "Kehrichtabfuhr im Winter", "DEUTSCH",
           "Ab dem 1. Dezember 2026 wird der Hauskehricht jeweils am Dienstag statt am Montag abgeholt. Bitte "
           "stellen Sie die gebührenpflichtigen Säcke bis spätestens 7.00 Uhr an den Strassenrand. Bei starkem "
           "Schneefall kann sich die Abfuhr um einen Tag verschieben.",
           "Freundliche Grüsse", "Gemeindeverwaltung Musterwil", "Fiktives Beispieldokument"],
    "fr": ["Commune de Musterwil", "Collecte des déchets en hiver", "FRANÇAIS",
           "À partir du 1er décembre 2026, les ordures ménagères seront collectées le mardi au lieu du lundi. "
           "Veuillez déposer les sacs taxés au bord de la route au plus tard à 7 h. En cas de fortes chutes de "
           "neige, la collecte peut être reportée d'un jour.", "Meilleures salutations"],
    "it": ["Comune di Musterwil", "Raccolta dei rifiuti in inverno", "ITALIANO",
           "Dal 1° dicembre 2026 i rifiuti domestici saranno raccolti il martedì invece del lunedì. Si prega di "
           "depositare i sacchi tassati sul bordo della strada entro le ore 7.00. In caso di forti nevicate, la "
           "raccolta può essere posticipata di un giorno.", "Cordiali saluti"],
    "en": ["ENGLISH", "Questions? The municipal office is open Monday to Friday from 8.00 to 11.30. You can also "
           "find the full collection calendar on our website.", "Fictitious sample document"],
}


def digits(text):
    return Counter(re.findall(r"\d+", text))


def test_translation_keeps_emails_numbers_dates_and_names(translator):
    names = protect.screen_names(t for texts in LETTER.values() for t in texts)
    assert names == {"Musterwil"}
    for src, texts in LETTER.items():
        for text, out in zip(texts, translator.translate(texts, src, "es", names=names)):
            assert "_" not in out, out
            assert digits(out) == digits(text), (text, out)
            if EMAIL in text:
                assert EMAIL in out
            if "Musterwil" in text:
                assert out.count("Musterwil") == text.count("Musterwil"), out


def test_translation_of_the_letter_reads_right(translator):
    t = lambda text, src: translator.translate([text], src, "es", names=frozenset({"Musterwil"}))[0]  # noqa: E731
    assert "1 de diciembre de 2026" in t(LETTER["it"][3], "it")  # not "10 de diciembre"
    assert "1 de diciembre de 2026" in t(LETTER["de"][7], "de")
    assert t("DEUTSCH", "de") == "ALEMÁN"  # the model alone says "ESPAÑOL"
    assert t("ITALIANO", "it") == "ITALIANO" and t("ENGLISH", "en") == "INGLÉS"
    swiss = t("Kehrichtabfuhr im Winter", "de").lower()
    assert "basura" in swiss or "residuos" in swiss  # Swiss "Kehricht" is rubbish, not "Audiencia"
    assert "playa" not in t("Bitte stellen Sie die Säcke an den Strassenrand.", "de")


def test_each_block_is_translated_from_its_own_language():
    """The engine groups the jobs by their own language, whatever the screen language is."""
    import threading

    from PySide6.QtCore import Qt

    from keept.engine import Engine, TranslationJob
    from keept.translate.translator import Translator

    used = []

    class Model:
        def __init__(self, pair):
            self.pair = pair

        def translate(self, sentences):
            used.append(self.pair)
            return [f"[{self.pair[0]}]{s}" for s in sentences]

    class Store:
        def get(self, s, t):
            return object()

        def download_progress(self, s, t):
            return None

    tr = Translator(loader=lambda s, t, p: Model((s, t)))
    tr.store = Store()
    engine = Engine(tr)
    out = {}
    engine.translated.connect(lambda session, key, text: out.__setitem__(key, text), Qt.DirectConnection)
    engine.set_active(1)
    jobs = [TranslationJob(1, LETTER["fr"][3], "fr"), TranslationJob(2, LETTER["it"][3], "it"),
            TranslationJob(3, LETTER["en"][1], "en")]
    engine.translate(1, jobs, "es")
    done = threading.Event()
    engine._tr_pool.submit(done.set)
    assert done.wait(10)
    assert out[1].startswith("[fr]") and out[2].startswith("[it]") and out[3].startswith("[en]")
    assert {p[0] for p in used} == {"fr", "it", "en"}
    engine.shutdown()
