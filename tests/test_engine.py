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
    assert engine.wait_translations(5)
    wait(engine._load_pool)
    first_translate = next(i for i, e in enumerate(log) if e[0] == "translate")
    # The job waited for its own model (loaded first, as the most likely pair), not for all.
    assert log.index(("load", ("de", "es"))) < first_translate
    assert log.count(("load", ("de", "es"))) == 1
    assert results == ["[de>es]Hallo."]
    engine.shutdown()


def test_languages_translate_in_parallel_and_queued_blocks_go_in_one_batch():
    calls = []

    class Slow:
        def __init__(self, pair):
            self.pair = pair

        def translate(self, sentences):
            calls.append((self.pair[0], len(sentences)))
            time.sleep(0.2)
            return [f"[{self.pair[0]}]{s}" for s in sentences]

    tr = Translator(loader=lambda s, t, p: Slow((s, t)))
    tr.store = FakeStore()
    engine = Engine(tr)
    out = {}
    engine.translated.connect(lambda session, key, text: out.__setitem__(key, text), Qt.DirectConnection)
    engine.set_active(3)
    for src in ("de", "fr", "it"):
        tr.prepare(src, "es")
    t0 = time.perf_counter()
    engine.translate(3, [TranslationJob(1, "Eins.", "de"), TranslationJob(2, "Un.", "fr"),
                         TranslationJob(3, "Uno.", "it")], "es")
    # Blocks read while the first German one is translated wait and then go together.
    engine.translate(3, [TranslationJob(4, "Zwei.", "de"), TranslationJob(5, "Drei.", "de")], "es")
    assert engine.wait_translations(5)
    elapsed = time.perf_counter() - t0
    assert out == {1: "[de]Eins.", 2: "[fr]Un.", 3: "[it]Uno.", 4: "[de]Zwei.", 5: "[de]Drei."}
    assert elapsed < 0.55  # three languages at once, then one German batch: 2 x 0.2 s
    assert [c for c in calls if c[0] == "de"] == [("de", 1), ("de", 2)]
    engine.shutdown()


def test_thread_budget_follows_the_cores(monkeypatch):
    from keept import cpu

    monkeypatch.setattr(cpu, "cores", lambda: 2)
    assert (cpu.recognizer_threads(), cpu.reread_helpers(), cpu.translation_threads(), cpu.translation_slots()) == (2, 0, 1, 1)
    monkeypatch.setattr(cpu, "cores", lambda: 12)
    assert (cpu.recognizer_threads(), cpu.reread_helpers(), cpu.translation_threads(), cpu.translation_slots()) == (4, 3, 2, 4)
