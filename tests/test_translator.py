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
    english_only = {("de", "en"), ("en", "de"), ("en", "es"), ("es", "en")}
    assert route("de", "es", english_only) == [("de", "en"), ("en", "es")]
    assert route("pt", "es") == [("pt", "en"), ("en", "es")]  # no direct OPUS-MT model
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

    english_only = frozenset({("de", "en"), ("en", "de"), ("en", "es"), ("es", "en")})
    monkeypatch.setattr(tmod.route, "__defaults__", (english_only,))
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


# -- model store ---------------------------------------------------------------
SPEC = {"url": "https://example.invalid/deu-eng/model.zip", "version": "test-1", "arch": "transformer",
        "download_bytes": 10, "target_label": None, "source": "test"}


def marian_package(extra=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in ("decoder.yml", "model.npz", "x.vocab.yml", "source.spm", "target.spm", "LICENSE", "train.log"):
            zf.writestr(name, b"data")
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


def opener_for(package, calls=None):
    def opener(url, timeout=0):
        if calls is not None:
            calls.append(url)
        return FakeResponse(package)

    return opener


@pytest.fixture
def fake_converter(monkeypatch):
    import keept.translate.models as models

    def convert(raw, out):
        assert (Path(raw) / "decoder.yml").exists() and (Path(raw) / "model.npz").exists()
        Path(out).mkdir(parents=True)
        (Path(out) / "model.bin").write_bytes(b"ct2")

    monkeypatch.setattr(models, "convert_marian", convert)


def test_store_installs_and_converts_opus_mt_package(tmp_path, fake_converter):
    calls = []
    store = ModelStore(tmp_path, opener=opener_for(marian_package(), calls), catalog={("de", "en"): SPEC})
    progress = []
    info = store.ensure("de", "en", lambda done, total: progress.append((done, total)))
    assert calls == [SPEC["url"]]
    assert info.version == "test-1"
    assert (info.path / "model" / "model.bin").read_bytes() == b"ct2"
    assert (info.path / "source.spm").exists() and (info.path / "LICENSE").exists()
    assert not (info.path / "marian").exists() and not (info.path / "train.log").exists()
    assert progress and progress[-1][0] == progress[-1][1]
    assert [m.src + m.tgt for m in store.installed()] == ["deen"]
    store.delete("de", "en")
    assert store.get("de", "en") is None


def test_old_argos_install_counts_as_missing(tmp_path):
    d = tmp_path / "de_en"
    (d / "model").mkdir(parents=True)
    (d / "model" / "model.bin").write_bytes(b"x")
    (d / "keept.json").write_text(json.dumps({"tokenizer": "spm", "version": "1.3"}), encoding="utf-8")
    store = ModelStore(tmp_path, catalog={("de", "en"): SPEC})
    assert store.get("de", "en") is None


def test_unknown_pair_is_unavailable(tmp_path):
    with pytest.raises(ModelError) as err:
        ModelStore(tmp_path, catalog={}).ensure("pt", "pl")
    assert err.value.kind == "unavailable"


def test_store_rejects_corrupt_download(tmp_path):
    store = ModelStore(tmp_path, opener=opener_for(b"not a zip"), catalog={("de", "en"): SPEC})
    with pytest.raises(ModelError) as err:
        store.ensure("de", "en")
    assert err.value.kind == "corrupt"
    assert store.get("de", "en") is None
    assert not any(p.name.endswith(".part") for p in tmp_path.iterdir())


def test_store_ignores_paths_outside_the_package(tmp_path, fake_converter):
    pkg = marian_package(extra={"../../evil.txt": b"x", "sub/../../evil2.txt": b"x"})
    store = ModelStore(tmp_path / "models", opener=opener_for(pkg), catalog={("de", "en"): SPEC})
    store.ensure("de", "en")
    assert not (tmp_path / "evil.txt").exists() and not (tmp_path / "evil2.txt").exists()


def test_network_error_is_reported_as_network(tmp_path, monkeypatch):
    import keept.translate.models as models

    monkeypatch.setattr(models.time, "sleep", lambda s: None)

    def opener(url, timeout=0, offset=0):
        raise OSError("no route to host")

    with pytest.raises(ModelError) as err:
        ModelStore(tmp_path, opener=opener, catalog={("de", "en"): SPEC}).ensure("de", "en")
    assert err.value.kind == "network"


def test_download_progress_is_visible_to_other_threads(tmp_path, fake_converter):
    seen = []
    store_ref = {}

    class Spy(FakeResponse):
        def read(self, n=-1):
            seen.append(store_ref["s"].download_progress("de", "en"))
            return super().read(n)

    store = ModelStore(tmp_path, opener=lambda url, timeout=0: Spy(marian_package()), catalog={("de", "en"): SPEC})
    store_ref["s"] = store
    store.ensure("de", "en")
    assert seen and all(s is not None for s in seen)
    assert store.download_progress("de", "en") is None


def test_catalog_covers_every_language_through_english():
    from keept.languages import CODES
    from keept.translate.models import CATALOG

    for code in CODES:
        if code != "en":
            assert (code, "en") in CATALOG and ("en", code) in CATALOG
    for src in CODES:
        for tgt in CODES:
            if src != tgt:
                assert 1 <= len(route(src, tgt)) <= 2


# -- OPUS-MT pre and post processing (no model download needed) -----------------
@pytest.fixture(scope="module")
def tiny_spm(tmp_path_factory):
    import sentencepiece as spm

    d = tmp_path_factory.mktemp("spm")
    corpus = d / "corpus.txt"
    lines = ["Último acceso al índice", "Índice de la única versión", "Única opción disponible",
             "Ñandú y niño en España", "El precio es de 250.- francos", "Gastos adicionales por mes",
             "Die Nebenkosten betragen 250.- Franken pro Monat", "Zuletzt verwendet am Montag"] * 20
    corpus.write_text("\n".join(lines), encoding="utf-8")
    spm.SentencePieceTrainer.train(input=str(corpus), model_prefix=str(d / "m"), vocab_size=60,
                                   character_coverage=1.0, model_type="unigram", minloglevel=2)
    return d / "m.model"


def test_marian_decoding_keeps_accented_capitals(tiny_spm):
    from keept.translate.models import MarianTokenizer

    tok = MarianTokenizer(tiny_spm, tiny_spm, "es")
    text = "Último Índice Única Ñandú"
    pieces = tok.encode(text)
    assert tok.decode(pieces + ["</s>"]) == text


def test_marian_source_is_moses_normalised_like_in_training(tiny_spm):
    from keept.translate.models import MarianTokenizer

    tok = MarianTokenizer(tiny_spm, tiny_spm, "de")
    # The OPUS-MT training data went through normalize-punctuation.perl: "–" became "-".
    assert tok.normalize("CHF 250.– pro Monat") == "CHF 250.- pro Monat"
    assert tok.normalize("„Hallo“ – sagte er") == '"Hallo" - sagte er'


def test_marian_target_label_is_prepended(tiny_spm):
    from keept.translate.models import MarianTokenizer

    tok = MarianTokenizer(tiny_spm, tiny_spm, "fr", target_label=">>por<<")
    assert tok.encode("Único")[0] == ">>por<<"


def test_sentences_are_nfc_normalised():
    import unicodedata

    decomposed = unicodedata.normalize("NFD", "Inténtalo más tarde.")
    assert split_sentences(decomposed) == ["Inténtalo más tarde."]


def test_download_resumes_after_a_dropped_connection(tmp_path, fake_converter, monkeypatch):
    import keept.translate.models as models

    monkeypatch.setattr(models.time, "sleep", lambda s: None)
    package = marian_package()
    requests = []

    class Dropping(FakeResponse):
        """Sends half the file and then times out, like a slow server."""

        def __init__(self, data, full):
            super().__init__(data)
            self.headers = {"Content-Length": str(len(full))}
            self.status = 200

        def read(self, n=-1):
            chunk = super().read(n)
            if not chunk:
                raise TimeoutError("The read operation timed out")
            return chunk

    class Partial(FakeResponse):
        status = 206

    def opener(url, timeout=0, offset=0):
        requests.append(offset)
        if offset == 0:
            return Dropping(package[: len(package) // 2], package)
        return Partial(package[offset:])

    store = ModelStore(tmp_path, opener=opener, catalog={("de", "en"): SPEC})
    info = store.ensure("de", "en")
    assert requests == [0, len(package) // 2]
    assert (info.path / "model" / "model.bin").exists()


def test_conversion_failure_in_child_process_is_reported(tmp_path):
    from keept.translate.models import convert_marian

    (tmp_path / "raw").mkdir()  # not a Marian model: the child process must fail cleanly
    with pytest.raises(ModelError) as err:
        convert_marian(tmp_path / "raw", tmp_path / "out")
    assert err.value.kind == "corrupt"


# -- models from the KeepT GitHub release ------------------------------------------
def converted_package():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("model/model.bin", b"ct2-int8")
        zf.writestr("model/config.json", b"{}")
        zf.writestr("model/shared_vocabulary.json", b"[]")
        for name in ("source.spm", "target.spm", "LICENSE", "README.md", "NOTICE.txt"):
            zf.writestr(name, b"x")
        zf.writestr("../evil.txt", b"x")
    return buf.getvalue()


def github_manifest(package, sha=None):
    import hashlib

    return {"base_url": "https://github.invalid/models-v1/", "models": {"de-en": {
        "file": "de-en.zip", "size": len(package), "sha256": sha or hashlib.sha256(package).hexdigest(),
        "opus_url": SPEC["url"], "target_label": None}}}


def test_model_comes_from_github_release_and_is_verified(tmp_path):
    package = converted_package()
    calls = []
    store = ModelStore(tmp_path / "models", opener=opener_for(package, calls), catalog={("de", "en"): SPEC},
                       manifest=github_manifest(package))
    info = store.ensure("de", "en")
    assert calls == ["https://github.invalid/models-v1/de-en.zip"]  # no OPUS-MT download, no conversion
    assert (info.path / "model" / "model.bin").read_bytes() == b"ct2-int8"
    assert (info.path / "NOTICE.txt").exists()
    assert not (tmp_path / "evil.txt").exists()
    assert json.loads((info.path / "keept.json").read_text())["source"] == "github"


def test_sha256_mismatch_discards_the_file(tmp_path):
    package = converted_package()
    store = ModelStore(tmp_path, opener=opener_for(package), catalog={("de", "en"): SPEC},
                       manifest=github_manifest(package, sha="0" * 64))
    with pytest.raises(ModelError) as err:
        store.ensure("de", "en")
    assert err.value.kind == "integrity"
    assert store.get("de", "en") is None
    assert not [p for p in tmp_path.iterdir() if p.name != "index.json"]  # nothing left behind


def test_falls_back_to_official_storage_when_github_fails(tmp_path, fake_converter, monkeypatch):
    import keept.translate.models as models

    monkeypatch.setattr(models.time, "sleep", lambda s: None)
    calls = []

    def opener(url, timeout=0, offset=0):
        calls.append(url)
        if "github" in url:
            raise OSError("github unreachable")
        return FakeResponse(marian_package())

    store = ModelStore(tmp_path, opener=opener, catalog={("de", "en"): SPEC},
                       manifest=github_manifest(converted_package()))
    info = store.ensure("de", "en")
    assert calls[-1] == SPEC["url"] and any("github" in c for c in calls)
    assert (info.path / "model" / "model.bin").read_bytes() == b"ct2"  # converted locally


def test_a_download_does_not_block_loading_another_pair():
    import threading
    import time as _time

    from keept.translate.translator import Translator

    release = threading.Event()

    class SlowStore:
        catalog = {}

        def ensure(self, src, tgt, progress=None):
            if (src, tgt) == ("en", "de"):
                release.wait(5)  # a long download of a model that is not needed right now
            return None

    tr = Translator(store=SlowStore())
    tr._default_loader = lambda s, t, p: (tr.store.ensure(s, t, p), object())[1]  # like the real one
    bg = threading.Thread(target=tr.model, args=(("en", "de"),))
    bg.start()
    _time.sleep(0.1)
    t0 = _time.perf_counter()
    tr.model(("en", "es"))  # on disk: must load right away
    assert _time.perf_counter() - t0 < 1.0
    release.set()
    bg.join()
