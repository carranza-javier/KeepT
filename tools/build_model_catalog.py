"""Build keept/translate/catalog.json: the OPUS-MT model KeepT uses for every language pair.

For each ordered pair of supported languages, pick a direct model from the official OPUS-MT
storage whose vocabulary can write every letter of the target language (some releases lack
capitals such as Ú or Ñ and can only output an unknown token for them). Preference: newest
Tatoeba transformer-big, then newest other Tatoeba model, then newest 2020 OPUS-MT model.
Only the vocabulary file is read from each remote zip (HTTP range requests). Pairs without any
direct model are left out and KeepT pivots through English for them.

    python tools/build_model_catalog.py
"""

from __future__ import annotations

import io
import json
import re
import zipfile
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keept.languages import LANGUAGES  # noqa: E402

TATOEBA = "https://object.pouta.csc.fi/Tatoeba-MT-models"
OPUS2020 = "https://object.pouta.csc.fi/OPUS-MT-models"
OUT = Path(__file__).resolve().parents[1] / "keept" / "translate" / "catalog.json"


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "KeepT-catalog-builder"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def listing(base: str, prefix: str) -> dict[str, int]:
    xml = get(f"{base}/?prefix={prefix}/")
    return {k: int(s) for k, s in re.findall(r"<Key>([^<]+)</Key>.*?<Size>(\d+)</Size>", xml)}


def date_of(name: str) -> str:
    dates = re.findall(r"(\d{4}-\d{2}-\d{2})", name)
    return dates[-1] if dates else ""


class HttpFile(io.RawIOBase):
    """Seekable read-only view of a remote file through HTTP range requests (for zipfile)."""

    def __init__(self, url: str, size: int):
        self.url, self.size, self.pos = url, size, 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def readinto(self, b):
        if self.pos >= self.size:
            return 0
        end = min(self.size, self.pos + len(b)) - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}",
                                                        "User-Agent": "KeepT-catalog-builder"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        b[:len(data)] = data
        self.pos += len(data)
        return len(data)


def vocabulary_chars(url: str, size: int) -> set[str]:
    with zipfile.ZipFile(io.BufferedReader(HttpFile(url, size), buffer_size=1 << 20)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".vocab.yml") and "/" not in n)
        return set(zf.read(name).decode("utf-8", "replace"))


def label_for(readme: str, zip_name: str, tgt3: str) -> str | None:
    """Target label like ">>por<<" when the README says the model needs one."""
    parts = re.split(r"^# ", readme, flags=re.M)
    section = next((p for p in parts if p.startswith(zip_name)), "")
    if "language token is required" not in section:
        return None
    labels = re.findall(r">>(\w+)<<", section.split("valid language labels:")[-1].splitlines()[0])
    if tgt3 in labels:
        return f">>{tgt3}<<"
    return f">>{labels[0]}<<" if labels else None


def candidates(src: str, tgt: str) -> list[dict]:
    """All direct models for a pair, in order of preference."""
    s3, t3 = LANGUAGES[src].iso3, LANGUAGES[tgt].iso3
    out = []
    files = listing(TATOEBA, f"{s3}-{t3}")
    zips = {k: v for k, v in files.items() if k.endswith(".zip") and "eval" not in k}
    if zips:
        metas = {k: (get(f"{TATOEBA}/{k[:-4]}.yml") if f"{k[:-4]}.yml" in files else "") for k in zips}
        readme = get(f"{TATOEBA}/{s3}-{t3}/README.md") if f"{s3}-{t3}/README.md" in files else ""

        def arch_of(k):
            m = re.search(r"modeltype:\s*(\S+)", metas[k])
            return m.group(1) if m else ("transformer-big" if "transformer-big" in k else "transformer")

        for k in sorted(zips, key=lambda k: (arch_of(k) == "transformer-big", date_of(k)), reverse=True):
            label = label_for(readme, k.split("/", 1)[1], t3)
            if not label and "use-target-labels:" in metas[k]:
                block = re.split(r"\n\S", metas[k].split("use-target-labels:")[-1])[0]
                labels = re.findall(r">>(\w+)<<", block)
                if labels:
                    label = f">>{t3}<<" if t3 in labels else f">>{labels[0]}<<"
            out.append({"url": f"{TATOEBA}/{k}", "version": k.split("/", 1)[1][:-4], "arch": arch_of(k),
                        "download_bytes": zips[k], "target_label": label, "source": "Tatoeba-MT-models"})
    files = listing(OPUS2020, f"{src}-{tgt}")
    zips = {k: v for k, v in files.items() if k.endswith(".zip") and "eval" not in k}
    if zips:
        readme = get(f"{OPUS2020}/{src}-{tgt}/README.md") if f"{src}-{tgt}/README.md" in files else ""
        for k in sorted(zips, key=date_of, reverse=True):
            out.append({"url": f"{OPUS2020}/{k}", "version": k.split("/", 1)[1][:-4],
                        "arch": "transformer-align" if "align" in readme else "transformer",
                        "download_bytes": zips[k], "target_label": label_for(readme, k.split("/", 1)[1], t3),
                        "source": "OPUS-MT-models"})
    return out


def pick(src: str, tgt: str):
    letters = set(LANGUAGES[tgt].letters + LANGUAGES[tgt].letters.upper())
    first = None
    for cand in candidates(src, tgt):
        first = first or cand
        missing = letters - vocabulary_chars(cand["url"], cand["download_bytes"])
        if not missing:
            return dict(cand, covers_target_letters=True)
        print(f"   skip {cand['version']}: vocabulary lacks {''.join(sorted(missing))}", flush=True)
    if first:
        print(f"   no model covers every letter, using {first['version']}", flush=True)
        return dict(first, covers_target_letters=False)
    return None


def main() -> int:
    catalog = {}
    for src in LANGUAGES:
        for tgt in LANGUAGES:
            if src == tgt:
                continue
            entry = pick(src, tgt)
            print(f"{src}->{tgt}: {entry['version'] + ' ' + entry['arch'] + ' ' + str(entry['download_bytes'] // 2**20) + ' MB' + (' label ' + entry['target_label'] if entry['target_label'] else '') if entry else 'no direct model'}",
                  flush=True)
            if entry:
                catalog[f"{src}-{tgt}"] = entry
    # A direct model that cannot write every letter of the target language is dropped when the
    # pivot through English can (both legs cover their target letters).
    for key, entry in list(catalog.items()):
        src, tgt = key.split("-")
        if entry["covers_target_letters"] or "en" in (src, tgt):
            continue
        a, b = catalog.get(f"{src}-en"), catalog.get(f"en-{tgt}")
        if a and b and a["covers_target_letters"] and b["covers_target_letters"]:
            print(f"{key}: direct model lacks letters, pivoting through English instead")
            del catalog[key]
    OUT.write_text(json.dumps(catalog, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote", OUT, len(catalog), "pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
