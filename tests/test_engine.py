import threading
import time

from PySide6.QtCore import Qt

from keept.engine import Engine, TranslationJob
from keept.translate.translator import Translator


class FakeStore:
    def get(self, src, tgt):
        return object()

    def download_progress(self, src, tgt):
        return None


class SlowModel:
    def __init__(self, pair, log):
        self.pair, self.log = pair, log

    def translate(self, sentences):
        self.log.append(("translate", self.pair))
        return [f"[{self.pair[0]}>{self.pair[1]}]{s}" for s in sentences]


def make_engine():
    log = []

    def loader(src, tgt, progress):
        time.sleep(0.05)
        log.append(("load", (src, tgt)))
        return SlowModel((src, tgt), log)

    tr = Translator(loader=loader)
    tr.store = FakeStore()
    return Engine(tr), tr, log


def wait(pool):
    done = threading.Event()
    pool.submit(done.set)
    assert done.wait(5)


def test_release_and_reload_most_likely_pair_first():
    engine, tr, log = make_engine()
    tr.prepare("de", "es")
    tr.prepare("en", "es")
    engine.release_models()
    wait(engine._tr_pool)
    assert tr.loaded_pairs() == []
    log.clear()
    engine.reload_models("es", sources=["en", "de"])
    wait(engine._load_pool)
    assert [e for e in log if e[0] == "load"] == [("load", ("en", "es")), ("load", ("de", "es"))]


def test_translation_requested_during_reload_waits_for_models():
    engine, tr, log = make_engine()
    results = []
    engine.translated.connect(lambda session, key, text: results.append(text), Qt.DirectConnection)
    engine.set_active(7)
    engine.reload_models("es", sources=["de", "en"])
    engine.translate(7, [TranslationJob(1, "Hallo.", "de")], "es")
    wait(engine._tr_pool)
    wait(engine._load_pool)
    first_translate = next(i for i, e in enumerate(log) if e[0] == "translate")
    # The job waited for its own model (loaded first, as the most likely pair), not for all.
    assert log.index(("load", ("de", "es"))) < first_translate
    assert log.count(("load", ("de", "es"))) == 1
    assert results == ["[de>es]Hallo."]
    engine.shutdown()
