"""OPUS-MT translation models: catalog, on demand download, local conversion and loading.

Every language pair uses an OPUS-MT model (University of Helsinki, CC BY 4.0) listed in
catalog.json (built by tools/build_model_catalog.py from the official OPUS-MT storage).
Nothing is bundled: a model is downloaded the first time a pair is needed, converted on the
user's machine to CTranslate2 int8 and kept in %LOCALAPPDATA%\\KeepT\\models.

Text goes through the same steps as in the OPUS-MT training pipeline (preprocess.sh):
Moses punctuation normalisation, then SentencePiece; output is decoded with SentencePiece.
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
from pathlib import Path
from typing import Callable

from ..paths import models_dir

log = logging.getLogger(__name__)

CATALOG_FILE = Path(__file__).with_name("catalog.json")
CATALOG: dict[tuple[str, str], dict] = {
    tuple(k.split("-")): v for k, v in json.loads(CATALOG_FILE.read_text(encoding="utf-8")).items()
}
KNOWN_PAIRS = frozenset(CATALOG)
USER_AGENT = "KeepT-model-downloader"
MARKER = "keept.json"

Progress = Callable[[int, int], None]  # (bytes done, bytes total)


class ModelError(Exception):
    """Base error with a `kind` used to pick a human message: network, disk, corrupt, unavailable."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


@dataclass
class InstalledModel:
    src: str
    tgt: str
    path: Path
    version: str
    size_bytes: int


def _dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


class ModelStore:
    def __init__(self, root: Path | None = None, opener=None, catalog: dict | None = None):
        self.root = Path(root) if root else models_dir()
        self.catalog = CATALOG if catalog is None else catalog
        self._locks: dict[tuple[str, str], threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._open = opener or self._urlopen
        self._progress: dict[tuple[str, str], tuple[int, int]] = {}

    @staticmethod
    def _urlopen(url: str, timeout: float = 20.0, offset: int = 0):
        headers = {"User-Agent": USER_AGENT}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)

    def pair_dir(self, src: str, tgt: str) -> Path:
        return self.root / f"{src}_{tgt}"

    def get(self, src: str, tgt: str) -> InstalledModel | None:
        """The installed model for a pair, if it is the OPUS-MT model of the catalog.
        Older installs (Argos packages, other versions) count as missing and are replaced."""
        d = self.pair_dir(src, tgt)
        try:
            meta = json.loads((d / MARKER).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        spec = self.catalog.get((src, tgt))
        if spec is None or meta.get("tokenizer") != "marian":
            return None
        if meta.get("url") not in (None, spec["url"]):
            return None
        if not (d / "model" / "model.bin").exists() or not (d / "source.spm").exists():
            return None
        return InstalledModel(src, tgt, d, meta.get("version", "?"), int(meta.get("size", 0)))

    def installed(self) -> list[InstalledModel]:
        return [m for m in (self.get(*p) for p in sorted(self.catalog)) if m]

    def delete(self, src: str, tgt: str) -> None:
        shutil.rmtree(self.pair_dir(src, tgt), ignore_errors=True)

    def download_progress(self, src: str, tgt: str) -> tuple[int, int] | None:
        """(done, total) bytes while this pair is being downloaded, else None."""
        return self._progress.get((src, tgt))

    def _lock(self, pair: tuple[str, str]) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(pair, threading.Lock())

    # -- download --------------------------------------------------------------
    def ensure(self, src: str, tgt: str, progress: Progress | None = None) -> InstalledModel:
        existing = self.get(src, tgt)
        if existing:
            return existing
        if (src, tgt) not in self.catalog:
            raise ModelError("unavailable", f"no model for {src}->{tgt}")
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
        spec = self.catalog[(src, tgt)]
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ModelError("disk", str(exc)) from exc
        t0 = time.perf_counter()
        fd, tmp_name = tempfile.mkstemp(prefix=f".{src}_{tgt}-", suffix=".part", dir=self.root)
        os.close(fd)
        tmp_zip = Path(tmp_name)
        try:
            self._fetch(spec["url"], tmp_zip, progress)
            log.info("Downloaded %s in %.1fs", spec["url"], time.perf_counter() - t0)
            return self._install(tmp_zip, src, tgt, spec)
        finally:
            tmp_zip.unlink(missing_ok=True)

    def _fetch(self, url: str, dest: Path, progress: Progress | None, attempts: int = 4) -> None:
        """Download `url` to `dest`. The OPUS-MT servers are sometimes slow: when the connection
        drops or times out, resume from the last byte (HTTP Range) instead of starting over."""
        done = 0
        total = 0
        last = 0.0
        error: Exception | None = None
        with open(dest, "wb") as out:
            for attempt in range(attempts):
                try:
                    resp = self._open(url, 30.0, done) if done else self._open(url, 30.0)
                    with resp:
                        length = int(resp.headers.get("Content-Length") or 0)
                        if done and getattr(resp, "status", 206) != 206:
                            out.seek(0)
                            out.truncate()
                            done = 0  # the server ignored the range: start again
                        total = total or (done + length)
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
                    if total and done < total:
                        raise OSError(f"connection closed at {done}/{total} bytes")
                    if progress:
                        progress(done, total or done)
                    return
                except OSError as exc:  # includes timeouts and dropped connections
                    if isinstance(exc, PermissionError) or getattr(exc, "errno", None) == 28:
                        raise ModelError("disk", str(exc)) from exc
                    error = exc
                    log.warning("Download interrupted at %d bytes (attempt %d/%d): %s", done, attempt + 1, attempts, exc)
                    time.sleep(min(5.0, 1.0 + attempt * 2))
        raise ModelError("network", str(error))

    def _install(self, zip_path: Path, src: str, tgt: str, spec: dict) -> InstalledModel:
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
                # Only flat names: nothing can be written outside the staging folder.
                keep = [n for n in zf.namelist() if "/" not in n and "\\" not in n and (
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
            (staging / MARKER).write_text(json.dumps({
                "src": src, "tgt": tgt, "version": spec["version"], "url": spec["url"],
                "tokenizer": "marian", "size": size,
            }), encoding="utf-8")
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
class MarianTokenizer:
    """The OPUS-MT pre and post processing: Moses punctuation normalisation of the source
    (training data was normalised this way, so for example "–" never appears in the vocabulary
    and must become "-"), SentencePiece with separate source and target models, an optional
    target language label (">>por<<") and SentencePiece decoding of the output."""

    def __init__(self, source: Path, target: Path, src_lang: str, target_label: str | None = None):
        import sentencepiece as spm
        from sacremoses import MosesPunctNormalizer

        self._src = spm.SentencePieceProcessor(model_file=str(source))
        self._tgt = spm.SentencePieceProcessor(model_file=str(target))
        self._norm = MosesPunctNormalizer(lang=src_lang, pre_replace_unicode_punct=True,
                                          post_remove_control_chars=True)
        self._label = target_label

    def normalize(self, text: str) -> str:
        return self._norm.normalize(text).strip()

    def encode(self, text: str) -> list[str]:
        tokens = self._src.encode(self.normalize(text), out_type=str)
        return [self._label, *tokens] if self._label else tokens

    def decode(self, tokens: list[str]) -> str:
        return self._tgt.decode([t for t in tokens if t != "</s>"])


class LoadedModel:
    def __init__(self, info: InstalledModel, threads: int, target_label: str | None = None):
        import ctranslate2

        t0 = time.perf_counter()
        self.info = info
        self.translator = ctranslate2.Translator(
            str(info.path / "model"), device="cpu", compute_type="int8", inter_threads=1, intra_threads=threads
        )
        self.tokenizer = MarianTokenizer(info.path / "source.spm", info.path / "target.spm", info.src, target_label)
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
            # Symbols outside the vocabulary (arrows, emoji...) must never print as "⁇". Letters
            # of the target language are always in the vocabulary: the catalog only uses models
            # whose vocabulary covers them (tools/build_model_catalog.py).
            disable_unk=True,
        )
        return [self.tokenizer.decode(r.hypotheses[0]) for r in results]
