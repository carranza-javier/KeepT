"""Compare translation systems on real sentences (quality + latency).

Systems:
  keept     the current KeepT pipeline (catalog model, direct or through English)
  opus      OPUS-MT 2020 direct de-es / es-de (Marian, converted to CTranslate2 int8)
  opusbig   OPUS-MT Tatoeba transformer-big 2022 direct deu-spa / spa-deu (int8)
  nllb      NLLB-200 distilled 600M (CTranslate2 int8)

    python tools/bench/benchmark_mt.py MODELS_DIR OUT.json
MODELS_DIR contains opus_de_es/, opus_es_de/, big_de_es/, big_es_de/ (converted) and nllb/.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import ctranslate2  # noqa: E402
import sentencepiece as spm  # noqa: E402

from keept.translate.translator import Translator, split_sentences  # noqa: E402

THREADS = max(1, min(8, (os.cpu_count() or 4) // 2))
NLLB_CODES = {"de": "deu_Latn", "es": "spa_Latn", "en": "eng_Latn"}


class MarianModel:
    def __init__(self, path: Path):
        self.tr = ctranslate2.Translator(str(path), device="cpu", compute_type="int8", intra_threads=THREADS)
        self.src = spm.SentencePieceProcessor(model_file=str(path / "source.spm"))
        self.tgt = spm.SentencePieceProcessor(model_file=str(path / "target.spm"))

    def translate(self, sentences):
        enc = [self.src.encode(s, out_type=str) for s in sentences]  # config adds </s>
        res = self.tr.translate_batch(enc, beam_size=2, max_batch_size=32, max_decoding_length=256, disable_unk=True)
        return [self.tgt.decode([t for t in r.hypotheses[0] if t != "</s>"]) for r in res]


class NllbModel:
    def __init__(self, path: Path, src: str, tgt: str):
        self.tr = ctranslate2.Translator(str(path), device="cpu", compute_type="int8", intra_threads=THREADS)
        self.sp = spm.SentencePieceProcessor(model_file=str(path / "sentencepiece.bpe.model"))
        self.src, self.tgt = NLLB_CODES[src], NLLB_CODES[tgt]

    def translate(self, sentences):
        enc = [[self.src] + self.sp.encode(s, out_type=str) + ["</s>"] for s in sentences]
        res = self.tr.translate_batch(enc, target_prefix=[[self.tgt]] * len(enc), beam_size=2,
                                      max_batch_size=32, max_decoding_length=256)
        return [self.sp.decode(r.hypotheses[0][1:]) for r in res]


class CurrentPipeline:
    def __init__(self, src: str, tgt: str):
        self.t = Translator()
        self.src, self.tgt = src, tgt
        self.t.prepare(src, tgt)

    def translate_texts(self, texts):
        self.t.clear_cache()
        return self.t.translate(texts, self.src, self.tgt)


def chrf(hyp: str, ref: str, n: int = 6, beta: float = 2.0) -> float:
    """Character n-gram F-score (chrF), whitespace removed, as in sacreBLEU."""
    h, r = hyp.replace(" ", ""), ref.replace(" ", "")
    precs, recs = [], []
    for k in range(1, n + 1):
        hg = Counter(h[i:i + k] for i in range(len(h) - k + 1))
        rg = Counter(r[i:i + k] for i in range(len(r) - k + 1))
        if not hg or not rg:
            continue
        match = sum((hg & rg).values())
        precs.append(match / sum(hg.values()))
        recs.append(match / sum(rg.values()))
    if not precs:
        return 0.0
    p, rr = statistics.mean(precs), statistics.mean(recs)
    if p + rr == 0:
        return 0.0
    return 100 * (1 + beta ** 2) * p * rr / (beta ** 2 * p + rr)


def run(system: str, direction: str, items, models_dir: Path, translator_pair) -> dict:
    src, tgt = direction.split("-")
    t0 = time.perf_counter()
    if system == "keept":
        model = CurrentPipeline(src, tgt)
        do = model.translate_texts
    else:
        if system == "nllb":
            m = NllbModel(models_dir / "nllb", src, tgt)
        else:
            m = MarianModel(models_dir / f"{'opus' if system == 'opus' else 'big'}_{src}_{tgt}")

        def do(texts, m=m):
            # Same sentence segmentation and batching as the app.
            return translator_pair(m, texts)

    load = time.perf_counter() - t0
    do(["Warm up sentence."])
    outs, times, scores = [], [], []
    for cat, text, ref in items:
        t = time.perf_counter()
        hyp = do([text])[0]
        times.append((time.perf_counter() - t) * 1000)
        outs.append(hyp)
        scores.append(chrf(hyp, ref))
    # A "first chunk" like the app: two blocks in one call
    t = time.perf_counter()
    do([items[0][1], items[1][1]])
    first_chunk = (time.perf_counter() - t) * 1000
    times_sorted = sorted(times)
    return {
        "system": system, "direction": direction, "load_s": round(load, 2),
        "chrf": round(statistics.mean(scores), 1),
        "chrf_by_cat": {c: round(statistics.mean(s for (cc, _, _), s in zip(items, scores) if cc == c), 1)
                        for c in sorted({i[0] for i in items})},
        "ms_median": round(statistics.median(times)), "ms_p90": round(times_sorted[int(len(times) * 0.9)]),
        "ms_max": round(max(times)), "first_chunk_ms": round(first_chunk),
        "outputs": outs, "scores": [round(s, 1) for s in scores],
    }


def main() -> int:
    models_dir = Path(sys.argv[1])
    out = Path(sys.argv[2])
    data = json.loads((Path(__file__).with_name("sentences.json")).read_text(encoding="utf-8"))
    def pair_fn(model, texts):
        """One model, sentence split like KeepT (without KeepT's protections)."""
        flat, spans = [], []
        for text in texts:
            parts = split_sentences(text)
            spans.append((len(flat), len(flat) + len(parts)))
            flat.extend(parts)
        out = model.translate(flat) if flat else []
        return [" ".join(out[a:b]).strip() for a, b in spans]
    systems = sys.argv[3].split(",") if len(sys.argv) > 3 else ["keept", "opus", "opusbig", "nllb"]
    results = []
    for direction, items in data.items():
        for system in systems:
            r = run(system, direction, items, models_dir, pair_fn)
            print(f"{direction} {system:8s} chrF {r['chrf']:5.1f} {r['chrf_by_cat']}  median {r['ms_median']} ms "
                  f"p90 {r['ms_p90']} ms max {r['ms_max']} ms  first chunk {r['first_chunk_ms']} ms  load {r['load_s']} s",
                  flush=True)
            results.append(r)
    out.write_text(json.dumps({"data": data, "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
