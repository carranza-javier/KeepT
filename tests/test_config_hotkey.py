import pytest

from keept.config import Config
from keept.hotkey import Hotkey


def test_hotkey_parse_and_format():
    hk = Hotkey.parse("ctrl + alt + t")
    assert str(hk) == "Ctrl+Alt+T"
    assert str(Hotkey.parse("Shift+Ctrl+F8")) == "Ctrl+Shift+F8"
    assert str(Hotkey.parse("Ctrl+Shift+space")) == "Ctrl+Shift+Space"


@pytest.mark.parametrize("bad", ["", "T", "Ctrl+", "Hyper+T", "Ctrl+Alt+Ñ"])
def test_hotkey_rejects_invalid(bad):
    with pytest.raises(ValueError):
        Hotkey.parse(bad)


def test_game_bar_conflict():
    assert Hotkey.parse("Win+Alt+T").conflicts_with_game_bar
    assert not Hotkey.parse("Ctrl+Alt+T").conflicts_with_game_bar


def test_win32_mapping():
    from keept.platform.win32 import MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, hotkey_to_win32

    assert hotkey_to_win32(Hotkey.parse("Ctrl+Alt+T")) == (MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord("T"))
    assert hotkey_to_win32(Hotkey.parse("Ctrl+F1"))[1] == 0x70


def test_config_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(hotkey="Ctrl+Shift+T", target_lang="es", autostart=False)
    cfg.save(path)
    loaded = Config.load(path)
    assert loaded == cfg


def test_config_tolerates_garbage(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    assert Config.load(path) == Config()
    path.write_text('{"target_lang": "ja", "unknown": 1, "last_source_lang": "xx"}', encoding="utf-8")
    cfg = Config.load(path)
    assert cfg.target_lang == "" and cfg.last_source_lang == "en"


def test_effective_target():
    assert Config().effective_target("de") == "de"
    assert Config().effective_target("ja") == "en"
    assert Config().effective_target("fr") == "fr"
    assert Config(target_lang="es").effective_target("de") == "es"


def test_hotkey_label_is_localised():
    from keept import i18n

    i18n.set_ui_lang("de")
    assert i18n.hotkey_label("Ctrl+Shift+T") == "Strg+Umschalt+T"
    i18n.set_ui_lang("es")
    assert i18n.hotkey_label("Ctrl+Shift+Space") == "Ctrl+Mayús+Espacio"
    i18n.set_ui_lang("en")
    assert i18n.hotkey_label("Ctrl+Alt+T") == "Ctrl+Alt+T"
