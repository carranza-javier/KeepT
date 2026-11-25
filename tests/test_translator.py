from pathlib import Path
import io
import json
import zipfile

import pytest

from keept.translate.models import ModelError, ModelStore
from keept.translate.translator import Translator, match_case, route, split_sentences


class FakeModel:
    """Marks each sentence with the pair so pivots can be checked."""

    def __init__(self, src, tgt):
        self.src, self.tgt = src, tgt
        self.calls = []

    def translate(self, sentences):
        self.calls.append(list(sentences))
        return [f"[{self.src}>{self.tgt}]{s}" for s in sentences]


@pytest.fixture
def translator(tmp_path):
    loaded = {}

    def loader(src, tgt, progress):
        loaded[(src, tgt)] = FakeModel(src, tgt)
        return loaded[(src, tgt)]

    t = Translator(ModelStore(tmp_path), loader=loader)
    t.loaded = loaded
    return t


def test_route_direct_and_pivot():
    assert route("de", "en") == [("de", "en")]
    assert route("es", "en") == [("es", "en")]
    assert route("de", "es") == [("de", "es")]  # direct OPUS-MT model
    assert route("es", "de") == [("es", "de")]
    argos_only = {("de", "en"), ("en", "de"), ("en", "es"), ("es", "en")}
    assert route("de", "es", argos_only) == [("de", "en"), ("en", "es")]
    assert route("en", "en") == []


def test_split_sentences():
    assert split_sentences("No se pudo guardar el archivo. Inténtalo de nuevo.") == [
        "No se pudo guardar el archivo.",
        "Inténtalo de nuevo.",
    ]
    assert split_sentences("Siehe z.B. Seite 30. Danach weiter.") == ["Siehe z.B. Seite 30. Danach weiter."]
    assert split_sentences("Geschlossen vom 24. Dezember bis 2. Januar. Danke!") == [
        "Geschlossen vom 24. Dezember bis 2. Januar.", "Danke!"]
    assert split_sentences("Ich bin vom 3. bis 14. Juli weg.") == ["Ich bin vom 3. bis 14. Juli weg."]
    assert split_sentences("Das kostet 120. Danach mehr.") == ["Das kostet 120.", "Danach mehr."]
    assert split_sentences("Version 2.5 is out! ¿Qué tal? Bien.") == ["Version 2.5 is out!", "¿Qué tal?", "Bien."]
    assert split_sentences("  ") == []


def test_translate_direct(translator):
    out = translator.translate(["Hallo Welt. Wie geht's?"], "de", "en")
    assert out == ["[de>en]Hallo Welt. [de>en]Wie geht's?"]


def test_translate_pivot_through_english(translator, monkeypatch):
    from keept.translate import translator as tmod

    argos_only = frozenset({("de", "en"), ("en", "de"), ("en", "es"), ("es", "en")})
    monkeypatch.setattr(tmod.route, "__defaults__", (argos_only,))
    out = translator.translate(["Hallo."], "de", "es")
    assert out == ["[en>es][de>en]Hallo."]
    assert set(translator.loaded) == {("de", "en"), ("en", "es")}


def test_translate_direct_german_spanish(translator):
    assert translator.translate(["Hallo."], "de", "es") == ["[de>es]Hallo."]


def test_batches_all_sentences_in_one_call(translator):
    translator.translate(["A one. A two.", "B one."], "en", "de")
    assert translator.loaded[("en", "de")].calls == [["A one.", "A two.", "B one."]]


def test_cache_avoids_retranslation(translator):
    translator.translate(["Same text."], "en", "es")
    translator.translate(["Same text.", "New text."], "en", "es")
    assert translator.loaded[("en", "es")].calls == [["Same text."], ["New text."]]


def test_same_language_is_identity(translator):
    assert translator.translate(["Hola"], "es", "es") == ["Hola"]
    assert translator.loaded == {}


def test_match_case():
    assert match_case("SETTINGS", "Ajustes") == "AJUSTES"
    assert match_case("Settings", "Ajustes") == "Ajustes"


# -- model store -------------------------------------------------------------
def make_package(prefix="translate-de_en-1_3/", tokenizer="sentencepiece.model", extra=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(prefix + "model/model.bin", b"bin")
        zf.writestr(prefix + "model/config.json", b"{}")
        zf.writestr(prefix + tokenizer, b"tok")
        zf.writestr(prefix + "stanza/de/tokenize/gsd.pt", b"big")
        zf.writestr(prefix + "metadata.json", b"{}")
        for name, data in (extra or {}).items():
            zf.writestr(name, data)
    return buf.getvalue()


class FakeResponse(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def fake_opener(package, index=None):
    index = index if index is not None else [
        {"from_code": "de", "to_code": "en", "package_version": "1.3", "links": ["https://example.invalid/de_en.argosmodel"]}
    ]

    def opener(url, timeout=0):
        if url.endswith("index.json"):
            return FakeResponse(json.dumps(index).encode())
        return FakeResponse(package)

    return opener


def test_store_installs_package_without_stanza(tmp_path):
    store = ModelStore(tmp_path, opener=fake_opener(make_package()))
    progress = []
    info = store.ensure("de", "en", lambda done, total: progress.append((done, total)))
    assert info.tokenizer == "spm" and info.version == "1.3"
    assert (info.path / "model" / "model.bin").read_bytes() == b"bin"
    assert not (info.path / "stanza").exists()
    assert progress and progress[-1][0] == progress[-1][1]
    assert [m.src + m.tgt for m in store.installed()] == ["deen"]
    store.delete("de", "en")
    assert store.get("de", "en") is None


def test_store_detects_bpe_tokenizer(tmp_path):
    store = ModelStore(tmp_path, opener=fake_opener(make_package("en_es/", "bpe.model")))
    assert store.ensure("de", "en").tokenizer == "bpe"


def test_store_rejects_corrupt_download(tmp_path):
    store = ModelStore(tmp_path, opener=fake_opener(b"not a zip"))
    with pytest.raises(ModelError) as err:
        store.ensure("de", "en")
    assert err.value.kind == "corrupt"
    assert store.get("de", "en") is None
    assert not any(p.name.endswith(".part") for p in tmp_path.iterdir())


def test_store_rejects_path_traversal(tmp_path):
    pkg = make_package(prefix="", extra={"model/../../evil.txt": b"x"})
    store = ModelStore(tmp_path / "models", opener=fake_opener(pkg))
    with pytest.raises(ModelError):
        store.ensure("de", "en")
    assert not (tmp_path / "evil.txt").exists()


def test_store_falls_back_to_builtin_links(tmp_path):
    calls = []

    def opener(url, timeout=0):
        calls.append(url)
        if url.endswith("index.json"):
            raise OSError("offline")
        return FakeResponse(make_package())

    ModelStore(tmp_path, opener=opener).ensure("de", "en")
    assert calls[-1] == "https://argos-net.com/v1/translate-de_en-1_3.argosmodel"


def test_network_error_is_reported_as_network(tmp_path):
    def opener(url, timeout=0):
        raise OSError("no route to host")

    with pytest.raises(ModelError) as err:
        ModelStore(tmp_path, opener=opener).ensure("de", "en")
    assert err.value.kind == "network"


def test_store_installs_marian_package_with_local_conversion(tmp_path, monkeypatch):
    import ctranslate2.converters.opus_mt as opus_mt

    class FakeConverter:
        def __init__(self, src_dir):
            self.src = Path(src_dir)
            assert (self.src / "decoder.yml").exists() and (self.src / "model.npz").exists()

        def convert(self, out, quantization, force):
            assert quantization == "int8"
            Path(out).mkdir(parents=True)
            (Path(out) / "model.bin").write_bytes(b"ct2")

    monkeypatch.setattr(opus_mt, "OpusMTConverter", FakeConverter)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in ("decoder.yml", "model.npz", "x.vocab.yml", "source.spm", "target.spm", "LICENSE", "train.log"):
            zf.writestr(name, b"data")
    store = ModelStore(tmp_path, opener=fake_opener(buf.getvalue()))
    info = store.ensure("de", "es")
    assert info.tokenizer == "marian" and info.version.startswith("tc-big")
    assert (info.path / "model" / "model.bin").read_bytes() == b"ct2"
    assert (info.path / "source.spm").exists() and (info.path / "LICENSE").exists()
    assert not (info.path / "marian").exists() and not (info.path / "train.log").exists()


def test_download_progress_is_visible_to_other_threads(tmp_path):
    seen = []
    package = make_package()
    store_ref = {}

    class Spy(FakeResponse):
        def read(self, n=-1):
            seen.append(store_ref["s"].download_progress("de", "en"))
            return super().read(n)

    def opener(url, timeout=0):
        if url.endswith("index.json"):
            return FakeResponse(json.dumps([]).encode())
        return Spy(package)

    store = ModelStore(tmp_path, opener=opener)
    store_ref["s"] = store
    store.ensure("de", "en")
    assert seen and all(s is not None for s in seen)
    assert store.download_progress("de", "en") is None


def test_restore_unknown_accented_capital():
    from keept.translate.models import restore_unknowns

    vocab = {"▁último", "▁última", "ltimo", "ltima", "▁uso", "▁vez", "▁U", "▁", "▁CHF", "▁250", ".", "▁por", "▁mes"}
    assert restore_unknowns(["▁", "<unk>", "ltimo", "▁uso"], vocab, "Zuletzt verwendet") == ["▁", "Ú", "ltimo", "▁uso"]
    # a character of the source that the vocabulary lacks
    out = restore_unknowns(["▁CHF", "▁250", ".", "<unk>", "▁por", "▁mes"], vocab, "CHF 250.– pro Monat")
    assert out[3] == "–"
    # nothing sensible: dropped
    assert restore_unknowns(["▁uso", "<unk>"], vocab, "uso") == ["▁uso"]


def test_marian_decode_keeps_restored_characters():
    from keept.translate.models import MarianTokenizer

    tok = MarianTokenizer.__new__(MarianTokenizer)
    assert tok.decode(["▁", "Ú", "ltimo", "▁uso", "</s>"]) == "Último uso"


def test_sentences_are_nfc_normalised():
    import unicodedata

    decomposed = unicodedata.normalize("NFD", "Inténtalo más tarde.")
    assert split_sentences(decomposed) == ["Inténtalo más tarde."]
