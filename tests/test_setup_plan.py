from types import SimpleNamespace

from keept.translate import setup_plan


class FakeStore:
    def __init__(self, installed, sizes):
        self._installed = set(installed)
        self.manifest = {"models": {f"{s}-{t}": {"size": n} for (s, t), n in sizes.items()}}

    def get(self, src, tgt):
        return object() if (src, tgt) in self._installed else None

    def installed(self):
        return [SimpleNamespace(src=s, tgt=t, size_bytes=1) for s, t in sorted(self._installed)]


def test_needed_pairs_pivot_through_english_once():
    pairs = setup_plan.needed_pairs("es", ["de", "en", "es", "pl"])
    assert ("en", "es") in pairs and ("de", "es") in pairs
    assert pairs.count(("en", "es")) == 1  # shared by en and by any pivot through English
    assert all(t == "es" or s != "en" for s, t in pairs)


def test_download_size_counts_only_missing_models():
    sizes = {("de", "es"): 80, ("en", "es"): 70, ("fr", "es"): 90}
    store = FakeStore({("en", "es")}, sizes)
    assert setup_plan.missing_pairs(store, "es", ["de", "en", "es"]) == [("de", "es")]
    assert setup_plan.download_bytes(store, "es", ["de", "en", "es"]) == 80
    assert setup_plan.download_bytes(store, "es", ["en", "es"]) == 0


def test_models_not_needed_any_more():
    store = FakeStore({("en", "es"), ("de", "es"), ("en", "de")}, {})
    assert sorted(setup_plan.unneeded_installed(store, "es", ["en", "es"])) == [("de", "es"), ("en", "de")]
