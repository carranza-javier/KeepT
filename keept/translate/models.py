"""Argos Translate model packages: index, download, cache on disk and loading.

The `argostranslate` package itself is not used (it pulls stanza and torch);
an .argosmodel is a zip with a CTranslate2 model plus a SentencePiece or
subword-nmt BPE tokenizer, which we load directly.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import threading
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

from ..paths import models_dir

log = logging.getLogger(__name__)

INDEX_URL = "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json"
# Used when the index cannot be fetched (links as published in the index on 2026-11-24).
FALLBACK_LINKS = {
    ("de", "en"): "https://argos-net.com/v1/translate-de_en-1_3.argosmodel",
    ("en", "de"): "https://argos-net.com/v1/translate-en_de-1_3.argosmodel",
    ("en", "es"): "https://argos-net.com/v1/translate-en_es-1_0.argosmodel",
    ("es", "en"): "https://argos-net.com/v1/translate-es_en-1_9.argosmodel",
}
# Direct German <-> Spanish: OPUS-MT Tatoeba transformer-big (CC-BY 4.0, University of Helsinki),
# downloaded from the official OPUS-MT storage and converted locally to CTranslate2 int8
# (better than the pivot through English in our benchmark, see DECISIONS.md).
MARIAN_MODELS = {
    ("de", "es"): ("https://object.pouta.csc.fi/Tatoeba-MT-models/deu-spa/"
                   "opusTCv20210807_transformer-big_2022-07-26.zip", "tc-big-2022-07-26"),
    ("es", "de"): ("https://object.pouta.csc.fi/Tatoeba-MT-models/spa-deu/"
                   "opusTCv20210807_transformer-big_2022-07-22.zip", "tc-big-2022-07-22"),
}
KNOWN_PAIRS = frozenset(FALLBACK_LINKS) | frozenset(MARIAN_MODELS)
USER_AGENT = "KeepT-model-downloader"
MARKER = "keept.json"

Progress = Callable[[int, int], None]  # (bytes done, bytes total)


class ModelError(Exception):
    """Base error with a `kind` used to pick a human message: network, disk, corrupt."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


@dataclass
class InstalledModel:
    src: str
    tgt: str
    path: Path
    version: str
    tokenizer: str  # "spm", "bpe" or "marian"
    size_bytes: int


def _dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


class ModelStore:
    def __init__(self, root: Path | None = None, opener=None):
        self.root = Path(root) if root else models_dir()
        self._locks: dict[tuple[str, str], threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._open = opener or self._urlopen
        self._progress: dict[tuple[str, str], tuple[int, int]] = {}

    @staticmethod
    def _urlopen(url: str, timeout: float = 20.0):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        return urllib.request.urlopen(req, timeout=timeout)

    def pair_dir(self, src: str, tgt: str) -> Path:
        return self.root / f"{src}_{tgt}"

    def get(self, src: str, tgt: str) -> InstalledModel | None:
        d = self.pair_dir(src, tgt)
        try:
            meta = json.loads((d / MARKER).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not (d / "model" / "model.bin").exists():
            return None
        return InstalledModel(src, tgt, d, meta.get("version", "?"), meta.get("tokenizer", "spm"), int(meta.get("size", 0)))

    def installed(self) -> list[InstalledModel]:
        out = []
        for src, tgt in sorted(KNOWN_PAIRS):
            m = self.get(src, tgt)
            if m:
                out.append(m)
        return out

    def delete(self, src: str, tgt: str) -> None:
        shutil.rmtree(self.pair_dir(src, tgt), ignore_errors=True)

    def download_progress(self, src: str, tgt: str) -> tuple[int, int] | None:
        """(done, total) bytes while this pair is being downloaded, else None."""
        return self._progress.get((src, tgt))

    def _lock(self, pair: tuple[str, str]) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(pair, threading.Lock())

    # -- index -----------------------------------------------------------------
    def resolve_link(self, src: str, tgt: str) -> tuple[str, str]:
        """Return (url, version) for a pair, from the online index or the built in fallback."""
        cache = self.root / "index.json"
        index = None
        try:
            with self._open(INDEX_URL, 10.0) as resp:
                index = json.loads(resp.read().decode("utf-8"))
            self.root.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(index), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - any network problem falls back
            log.info("Model index not reachable (%s), using cached or built in links", exc)
            try:
                index = json.loads(cache.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                index = None
        if isinstance(index, list):
            for pkg in index:
                if pkg.get("from_code") == src and pkg.get("to_code") == tgt:
                    links = [l for l in pkg.get("links", []) if l.startswith("https://")]
                    if links:
                        return links[0], str(pkg.get("package_version", "?"))
        if (src, tgt) in FALLBACK_LINKS:
            return FALLBACK_LINKS[(src, tgt)], "fallback"
        raise ModelError("unavailable", f"no model for {src}->{tgt}")

    # -- download --------------------------------------------------------------
    def ensure(self, src: str, tgt: str, progress: Progress | None = None) -> InstalledModel:
        existing = self.get(src, tgt)
        if existing:
            return existing
        with self._lock((src, tgt)):
            existing = self.get(src, tgt)
            if existing:
                return existing
            self._progress[(src, tgt)] = (0, 0)

            def track(done: int, total: int) -> None:
                self._progress[(src, tgt)] = (done, total)
                if progress:
                    progress(done, total)

            try:
                return self._download_and_install(src, tgt, track)
            finally:
                self._progress.pop((src, tgt), None)

    def _download_and_install(self, src: str, tgt: str, progress: Progress | None) -> InstalledModel:
        marian = (src, tgt) in MARIAN_MODELS
        url, version = MARIAN_MODELS[(src, tgt)] if marian else self.resolve_link(src, tgt)
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ModelError("disk", str(exc)) from exc
        t0 = time.perf_counter()
        fd, tmp_name = tempfile.mkstemp(prefix=f".{src}_{tgt}-", suffix=".part", dir=self.root)
        os.close(fd)
        tmp_zip = Path(tmp_name)
        try:
            self._fetch(url, tmp_zip, progress)
            log.info("Downloaded %s in %.1fs", url, time.perf_counter() - t0)
            if marian:
                return self._install_marian(tmp_zip, src, tgt, version)
            return self._install_zip(tmp_zip, src, tgt, version)
        finally:
            tmp_zip.unlink(missing_ok=True)

    def _fetch(self, url: str, dest: Path, progress: Progress | None) -> None:
        try:
            with self._open(url, 30.0) as resp, open(dest, "wb") as out:
                total = int(resp.headers.get("Content-Length") or 0)
                done = 0
                last = 0.0
                while True:
                    chunk = resp.read(1 << 18)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    now = time.monotonic()
                    if progress and (now - last > 0.1):
                        progress(done, total)
                        last = now
                if progress:
                    progress(done, total or done)
                if total and done != total:
                    raise ModelError("network", f"incomplete download ({done}/{total} bytes)")
        except ModelError:
            raise
        except OSError as exc:
            kind = "disk" if isinstance(exc, (PermissionError,)) or getattr(exc, "errno", None) == 28 else "network"
            raise ModelError(kind, str(exc)) from exc

    def _install_zip(self, zip_path: Path, src: str, tgt: str, version: str) -> InstalledModel:
        final = self.pair_dir(src, tgt)
        staging = Path(tempfile.mkdtemp(prefix=f".{src}_{tgt}-", dir=self.root))
        try:
            try:
                zf = zipfile.ZipFile(zip_path)
            except zipfile.BadZipFile as exc:
                raise ModelError("corrupt", "downloaded file is not a valid model package") from exc
            with zf:
                names = zf.namelist()
                bins = [n for n in names if n.endswith("model/model.bin")]
                if not bins:
                    raise ModelError("corrupt", "model.bin not found in package")
                prefix = bins[0][: -len("model/model.bin")]
                wanted = []
                for name in names:
                    if not name.startswith(prefix) or name.endswith("/"):
                        continue
                    rel = name[len(prefix):]
                    if rel.startswith("model/") or rel in ("sentencepiece.model", "bpe.model", "metadata.json", "README.md"):
                        wanted.append((name, rel))
                for name, rel in wanted:
                    rel_path = PurePosixPath(rel)
                    if rel_path.is_absolute() or ".." in rel_path.parts:
                        raise ModelError("corrupt", f"unsafe path in package: {name}")
                    target = staging.joinpath(*rel_path.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(name) as fsrc, open(target, "wb") as fdst:
                        shutil.copyfileobj(fsrc, fdst, 1 << 20)
            if (staging / "sentencepiece.model").exists():
                tokenizer = "spm"
            elif (staging / "bpe.model").exists():
                tokenizer = "bpe"
            else:
                raise ModelError("corrupt", "no tokenizer in package")
            size = _dir_size(staging)
            (staging / MARKER).write_text(
                json.dumps({"src": src, "tgt": tgt, "version": version, "tokenizer": tokenizer, "size": size}),
                encoding="utf-8",
            )
            if final.exists():
                shutil.rmtree(final, ignore_errors=True)
            staging.rename(final)
        except OSError as exc:
            raise ModelError("disk", str(exc)) from exc
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
        model = self.get(src, tgt)
        assert model is not None
        return model


    def _install_marian(self, zip_path: Path, src: str, tgt: str, version: str) -> InstalledModel:
        """Extract an OPUS-MT Marian package and convert it to CTranslate2 int8."""
        final = self.pair_dir(src, tgt)
        staging = Path(tempfile.mkdtemp(prefix=f".{src}_{tgt}-", dir=self.root))
        raw = staging / "marian"
        try:
            try:
                zf = zipfile.ZipFile(zip_path)
            except zipfile.BadZipFile as exc:
                raise ModelError("corrupt", "downloaded file is not a valid model package") from exc
            with zf:
                keep = [n for n in zf.namelist() if "/" not in n and (
                    n.endswith((".npz", ".spm", "decoder.yml", ".vocab.yml")) or n in ("LICENSE", "README.md"))]
                if not any(n.endswith(".npz") for n in keep) or "decoder.yml" not in keep:
                    raise ModelError("corrupt", "not an OPUS-MT package")
                raw.mkdir()
                for name in keep:
                    with zf.open(name) as fsrc, open(raw / name, "wb") as fdst:
                        shutil.copyfileobj(fsrc, fdst, 1 << 20)
            t0 = time.perf_counter()
            try:
                from ctranslate2.converters.opus_mt import OpusMTConverter

                OpusMTConverter(str(raw)).convert(str(staging / "model"), quantization="int8", force=True)
            except Exception as exc:  # noqa: BLE001
                raise ModelError("corrupt", f"conversion failed: {exc}") from exc
            log.info("Converted %s->%s to CTranslate2 int8 in %.1fs", src, tgt, time.perf_counter() - t0)
            for name in ("source.spm", "target.spm", "LICENSE", "README.md"):
                if (raw / name).exists():
                    shutil.copy(raw / name, staging / name)
            shutil.rmtree(raw, ignore_errors=True)
            size = _dir_size(staging)
            (staging / MARKER).write_text(
                json.dumps({"src": src, "tgt": tgt, "version": version, "tokenizer": "marian", "size": size}),
                encoding="utf-8",
            )
            if final.exists():
                shutil.rmtree(final, ignore_errors=True)
            staging.rename(final)
        except OSError as exc:
            raise ModelError("disk", str(exc)) from exc
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
        model = self.get(src, tgt)
        assert model is not None
        return model


# -- loading -------------------------------------------------------------------
class SentencePieceTokenizer:
    def __init__(self, path: Path):
        import sentencepiece as spm

        self._sp = spm.SentencePieceProcessor(model_file=str(path))

    def encode(self, text: str) -> list[str]:
        return self._sp.encode(text, out_type=str)

    def decode(self, tokens: list[str]) -> str:
        return self._sp.decode(tokens)


class BPETokenizer:
    """Moses tokenization + subword-nmt BPE, as used by OPUS-MT based Argos packages."""

    def __init__(self, path: Path, src: str, tgt: str):
        from sacremoses import MosesDetokenizer, MosesPunctNormalizer, MosesTokenizer
        from subword_nmt.apply_bpe import BPE

        with open(path, encoding="utf-8") as f:
            self._bpe = BPE(f)
        self._norm = MosesPunctNormalizer(src)
        self._tok = MosesTokenizer(src)
        self._detok = MosesDetokenizer(tgt)

    def encode(self, text: str) -> list[str]:
        tokens = self._tok.tokenize(self._norm.normalize(text), escape=True)
        return self._bpe.segment_tokens(tokens)

    def decode(self, tokens: list[str]) -> str:
        return self._detok.detokenize(" ".join(tokens).replace("@@ ", "").split(" "))


UNK = "<unk>"
# Capital letters that some OPUS-MT vocabularies lack although the lowercase forms exist
# (the de<->es transformer-big models have no Í, Ó, Ú or Ñ).
_ACCENTED_CAPITALS = "ÚÍÓÑÁÉÜ"


def load_vocabulary(model_dir: Path) -> set[str]:
    for name in ("shared_vocabulary.json", "shared_vocabulary.txt", "target_vocabulary.json", "target_vocabulary.txt"):
        path = model_dir / name
        if path.exists():
            text = path.read_text(encoding="utf-8")
            return set(json.loads(text)) if name.endswith(".json") else set(text.split("\n"))
    return set()


def restore_unknowns(tokens: list[str], vocab: set[str], source: str) -> list[str]:
    """Replace <unk> tokens the model produced for characters missing from its vocabulary.

    The model knows *where* the character goes ("▁", <unk>, "ltimo" is "Último"), so:
    1. at the start of a word, try the accented capitals whose lowercase form makes a
       vocabulary word with the next piece ("▁último" -> "Ú");
    2. otherwise use, in order, characters of the source text that the vocabulary lacks
       (for example "–" in "CHF 250.–");
    3. otherwise drop it.
    """
    vocab_chars = set("".join(vocab))
    spare = [c for c in source if not c.isspace() and c not in vocab_chars]
    prefixes = None
    out: list[str] = []
    for i, tok in enumerate(tokens):
        if tok != UNK:
            out.append(tok)
            continue
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        word_start = not out or out[-1] == "▁" or out[-1].endswith(("▁", " "))
        choice = ""
        if word_start and nxt and not nxt.startswith("▁"):
            for cap in _ACCENTED_CAPITALS:
                low = "▁" + cap.lower() + nxt
                if low in vocab:
                    choice = cap
                    break
            if not choice:
                if prefixes is None:
                    prefixes = sorted(vocab)
                import bisect

                for cap in _ACCENTED_CAPITALS:
                    stem = "▁" + cap.lower() + nxt
                    j = bisect.bisect_left(prefixes, stem)
                    if j < len(prefixes) and prefixes[j].startswith(stem):
                        choice = cap
                        break
        if not choice and spare:
            choice = spare.pop(0)
        if choice:
            out.append(choice)
    return out


class MarianTokenizer:
    """OPUS-MT: separate SentencePiece models for source and target. The converted model
    configuration appends the end of sentence token to the source itself."""

    def __init__(self, source: Path, target: Path):
        import sentencepiece as spm

        self._src = spm.SentencePieceProcessor(model_file=str(source))
        self._tgt = spm.SentencePieceProcessor(model_file=str(target))

    def encode(self, text: str) -> list[str]:
        return self._src.encode(text, out_type=str)

    def decode(self, tokens: list[str]) -> str:
        # Plain join instead of SentencePiece decoding, so restored characters that are not in
        # the vocabulary survive (SentencePiece would turn them back into an unknown marker).
        return "".join(t for t in tokens if t != "</s>").replace("▁", " ").strip()


class LoadedModel:
    def __init__(self, info: InstalledModel, threads: int):
        import ctranslate2

        t0 = time.perf_counter()
        self.info = info
        self.translator = ctranslate2.Translator(
            str(info.path / "model"), device="cpu", compute_type="int8", inter_threads=1, intra_threads=threads
        )
        self.vocab: set[str] | None = None
        if info.tokenizer == "marian":
            self.tokenizer = MarianTokenizer(info.path / "source.spm", info.path / "target.spm")
            self.vocab = load_vocabulary(info.path / "model")
        elif info.tokenizer == "bpe":
            self.tokenizer = BPETokenizer(info.path / "bpe.model", info.src, info.tgt)
        else:
            self.tokenizer = SentencePieceTokenizer(info.path / "sentencepiece.model")
        log.info("Loaded model %s->%s in %.2fs", info.src, info.tgt, time.perf_counter() - t0)

    def translate(self, sentences: list[str], beam_size: int = 2) -> list[str]:
        if not sentences:
            return []
        encoded = [self.tokenizer.encode(s) for s in sentences]
        longest = max(len(e) for e in encoded)
        results = self.translator.translate_batch(
            encoded,
            beam_size=beam_size,
            max_batch_size=32,
            max_decoding_length=min(512, int(longest * 2.5) + 16),
            repetition_penalty=1.05,
            # Marian models: let the model mark missing characters and restore them below.
            # Others: never produce the unknown marker.
            disable_unk=self.vocab is None,
        )
        if self.vocab is not None:
            return [self.tokenizer.decode(restore_unknowns(r.hypotheses[0], self.vocab, src))
                    for r, src in zip(results, sentences)]
        return [self.tokenizer.decode(r.hypotheses[0]) for r in results]
