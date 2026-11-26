"""Build keept/translate/swiss_places.txt from the official list of Swiss municipalities.

    python tools/build_swiss_places.py [communes.csv]

Source: Swiss Federal Statistical Office (BFS/OFS), "Official commune register of Switzerland"
(https://www.agvchapp.bfs.admin.ch), open data, free use with the source named.

KeepT keeps these names unchanged when translating (unless the plain translation already
keeps them). Names that are also ordinary words or that have an exonym are left out, so
"Wald", "Horn" or "Bern" ("Berna") are still translated: a name is dropped when it, or its
lower case form, is a single piece in the source vocabulary of the installed German, French,
Italian or English models (common words and big cities are; village names are not).
"""
from __future__ import annotations

import csv
import io
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "keept" / "translate" / "swiss_places.txt"
URL = "https://www.agvchapp.bfs.admin.ch/api/communes/snapshot?date=01-01-2026"
# Names with an exonym in other languages (Zürich -> Zúrich, Genève -> Ginebra...).
EXONYMS = {"Zürich", "Luzern", "Genève", "Basel", "Bern", "Fribourg", "Neuchâtel", "St. Gallen",
           "Schaffhausen", "Solothurn", "Sion", "Chur", "Biel", "Bienne", "Lausanne", "Lugano",
           "Winterthur", "Thun", "Zug", "Glarus", "Sitten", "Delémont", "Locarno", "Bellinzona"}


def read_csv(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    req = urllib.request.Request(URL, headers={"User-Agent": "KeepT-build"})
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8")


def main() -> int:
    import sentencepiece as spm

    rows = [r for r in csv.DictReader(io.StringIO(read_csv(sys.argv[1] if len(sys.argv) > 1 else None)))
            if r["Level"] == "3" and not r["ValidTo"]]
    names: set[str] = set()
    for r in rows:
        name = re.sub(r"\s*\(.*?\)\s*$", "", r["Name"]).strip()
        for part in name.split("/"):  # "Biel/Bienne", "Domat/Ems"
            part = part.strip()
            if len(part) >= 4:
                names.add(part)
    models = Path(os.environ["LOCALAPPDATA"]) / "KeepT" / "models"
    vocabs = [spm.SentencePieceProcessor(model_file=str(p)) for p in models.glob("*/source.spm")]
    if not vocabs:
        print("No installed models: install German, French or Italian first", file=sys.stderr)
        return 1

    def single(word: str) -> bool:
        return any(len(sp.encode(word, out_type=str)) == 1 for sp in vocabs)

    keep = sorted(n for n in names if n not in EXONYMS and not (" " not in n and (single(n) or single(n.lower()))))
    OUT.write_text("# Swiss municipalities (BFS official commune register, 2026-01-01), see tools/build_swiss_places.py\n"
                   + "\n".join(keep) + "\n", encoding="utf-8")
    print(f"{len(rows)} communes, {len(keep)} names written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
