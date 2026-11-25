import re

from keept import i18n
from keept.languages import CODES


def test_ui_covers_every_supported_language():
    assert set(i18n.UI_LANGS) == set(CODES)


def test_every_text_exists_in_every_language_with_the_same_placeholders():
    ph = re.compile(r"\{(\w+)\}")
    for key, entry in i18n._STRINGS.items():
        assert set(entry) == set(i18n.UI_LANGS), key
        want = set(ph.findall(entry["en"]))
        for lang, text in entry.items():
            assert text.strip(), (key, lang)
            assert set(ph.findall(text)) == want, (key, lang)
            assert "—" not in text, (key, lang)  # no em dashes


def test_unknown_windows_language_falls_back_to_english():
    i18n.set_ui_lang("ja")
    assert i18n.ui_lang() == "en" and i18n.tr("copy") == "Copy"
    i18n.set_ui_lang("pl")
    assert i18n.tr("copy") == "Kopiuj"
    assert i18n.hotkey_label("Ctrl+Shift+Space") == "Ctrl+Shift+Spacja"
    i18n.set_ui_lang("fr")
    assert i18n.hotkey_label("Ctrl+Shift+Space") == "Ctrl+Maj+Espace"
    i18n.set_ui_lang("en")
