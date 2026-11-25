"""Convert the catalog's OPUS-MT models to CTranslate2 int8 once and publish them as assets of a
GitHub release (default tag models-v1), with a manifest of sizes and SHA-256 hashes.

KeepT downloads models from that release and verifies the SHA-256 before using them; the
official OPUS-MT storage is only a fallback. Run it from GitHub Actions (.github/workflows/
models.yml) or locally:

    GITHUB_TOKEN=... python tools/publish_models.py --tag models-v1 [--pairs de-es,en-es] [--repo owner/name]

The script is resumable: models already present in the release (and in its manifest) are skipped.
It writes the manifest to keept/translate/models_manifest.json as well, so it can be committed:
the app pins the hashes it ships with.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "keept" / "translate" / "catalog.json"
MANIFEST_OUT = ROOT / "keept" / "translate" / "models_manifest.json"
API = "https://api.github.com"
UA = "KeepT-model-publisher"

NOTICE = """This package contains the OPUS-MT model "{version}" ({src} -> {tgt}) by the Language Technology
Research Group at the University of Helsinki (Jörg Tiedemann, Santhosh Thottingal et al.),
licensed under CC BY 4.0: https://creativecommons.org/licenses/by/4.0/

Original: {url}

Changes made by KeepT: the Marian model was converted to the CTranslate2 format with int8
quantization (ctranslate2 {ct2}). The SentencePiece models, LICENSE and README of the original
package are included unchanged.
"""


def log(*args) -> None:
    print(*args, flush=True)


class GitHub:
    def __init__(self, repo: str, token: str):
        self.repo, self.token = repo, token

    def call(self, method: str, url: str, data: bytes | None = None, ctype: str = "application/json",
             length: int | None = None, body=None):
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
                   "User-Agent": UA, "X-GitHub-Api-Version": "2022-11-28"}
        if data is not None or body is not None:
            headers["Content-Type"] = ctype
        if length is not None:
            headers["Content-Length"] = str(length)
        req = urllib.request.Request(url, data=data if data is not None else body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=600) as r:
            raw = r.read()
            return json.loads(raw) if raw else None

    def release(self, tag: str) -> dict:
        try:
            return self.call("GET", f"{API}/repos/{self.repo}/releases/tags/{tag}")
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        body = {
            "tag_name": tag, "name": "Translation models (OPUS-MT, CTranslate2 int8)",
            "body": ("OPUS-MT translation models converted to CTranslate2 int8 for KeepT. KeepT downloads "
                     "them on demand and checks the SHA-256 listed in manifest.json.\n\n"
                     "Models by the Language Technology Research Group, University of Helsinki (OPUS-MT), "
                     "CC BY 4.0. Each zip contains the original LICENSE, README and a NOTICE describing the "
                     "conversion."),
            "prerelease": True, "make_latest": "false",
        }
        return self.call("POST", f"{API}/repos/{self.repo}/releases", json.dumps(body).encode())

    def assets(self, release: dict) -> dict[str, dict]:
        out, page = {}, 1
        while True:
            items = self.call("GET", f"{API}/repos/{self.repo}/releases/{release['id']}/assets?per_page=100&page={page}")
            out.update({a["name"]: a for a in items})
            if len(items) < 100:
                return out
            page += 1

    def delete_asset(self, asset: dict) -> None:
        self.call("DELETE", f"{API}/repos/{self.repo}/releases/assets/{asset['id']}")

    def upload(self, release: dict, path: Path, name: str, ctype: str) -> dict:
        base = release["upload_url"].split("{")[0]
        url = f"{base}?name={urllib.parse.quote(name)}"
        for attempt in range(4):
            try:
                with open(path, "rb") as f:
                    return self.call("POST", url, ctype=ctype, length=path.stat().st_size, body=f)
            except (urllib.error.URLError, OSError) as exc:
                log(f"  upload failed ({exc}), retrying")
                time.sleep(5 * (attempt + 1))
                # a half uploaded asset may be left in "starter" state: remove it before retrying
                stale = self.assets(release).get(name)
                if stale:
                    self.delete_asset(stale)
        raise RuntimeError(f"could not upload {name}")


def download(url: str, dest: Path) -> None:
    done = 0
    with open(dest, "wb") as out:
        for attempt in range(6):
            try:
                headers = {"User-Agent": UA}
                if done:
                    headers["Range"] = f"bytes={done}-"
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                    if done and r.status != 206:
                        out.seek(0)
                        out.truncate()
                        done = 0
                    total = done + int(r.headers.get("Content-Length") or 0)
                    while chunk := r.read(1 << 20):
                        out.write(chunk)
                        done += len(chunk)
                if not total or done >= total:
                    return
            except (urllib.error.URLError, OSError) as exc:
                log(f"  download interrupted at {done} bytes: {exc}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"could not download {url}")


def build_package(src: str, tgt: str, spec: dict, work: Path) -> Path:
    import ctranslate2
    from ctranslate2.converters.opus_mt import OpusMTConverter

    raw_zip = work / "raw.zip"
    t0 = time.time()
    download(spec["url"], raw_zip)
    log(f"  downloaded {raw_zip.stat().st_size / 2**20:.0f} MB in {time.time() - t0:.0f}s")
    raw = work / "marian"
    raw.mkdir()
    with zipfile.ZipFile(raw_zip) as zf:
        for n in zf.namelist():
            if "/" not in n and (n.endswith((".npz", ".spm", "decoder.yml", ".vocab.yml")) or n in ("LICENSE", "README.md")):
                zf.extract(n, raw)
    raw_zip.unlink()
    out = work / "pkg"
    OpusMTConverter(str(raw)).convert(str(out / "model"), quantization="int8", force=True)
    for name in ("source.spm", "target.spm", "LICENSE", "README.md"):
        if (raw / name).exists():
            shutil.copy(raw / name, out / name)
    (out / "NOTICE.txt").write_text(NOTICE.format(version=spec["version"], src=src, tgt=tgt, url=spec["url"],
                                                  ct2=ctranslate2.__version__), encoding="utf-8")
    shutil.rmtree(raw)
    pkg = work / f"{src}-{tgt}.zip"
    with zipfile.ZipFile(pkg, "w") as zf:
        for f in sorted(out.rglob("*")):
            if f.is_file():
                rel = f.relative_to(out).as_posix()
                # model.bin is int8 data that barely compresses: store it, deflate the rest
                zf.write(f, rel, compress_type=zipfile.ZIP_STORED if rel.endswith(".bin") else zipfile.ZIP_DEFLATED)
    shutil.rmtree(out)
    return pkg


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="models-v1")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "carranza-javier/KeepT"))
    ap.add_argument("--pairs", default="", help="comma separated, e.g. de-es,en-es (default: whole catalog)")
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is required")
    gh = GitHub(args.repo, token)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    pairs = [p for p in (args.pairs.split(",") if args.pairs else catalog) if p]
    release = gh.release(args.tag)
    assets = gh.assets(release)
    manifest = {"release": args.tag, "repo": args.repo,
                "base_url": f"https://github.com/{args.repo}/releases/download/{args.tag}/", "models": {}}
    if "manifest.json" in assets:
        req = urllib.request.Request(assets["manifest.json"]["browser_download_url"], headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            manifest["models"] = json.loads(r.read())["models"]

    def publish_manifest() -> None:
        MANIFEST_OUT.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        current = gh.assets(release).get("manifest.json")
        if current:
            gh.delete_asset(current)
        gh.upload(release, MANIFEST_OUT, "manifest.json", "application/json")

    for i, key in enumerate(pairs, 1):
        spec = catalog[key]
        name = f"{key}.zip"
        entry = manifest["models"].get(key)
        if name in assets and entry and entry.get("opus_url") == spec["url"] and assets[name]["size"] == entry["size"]:
            log(f"[{i}/{len(pairs)}] {key}: already published, skipping")
            continue
        log(f"[{i}/{len(pairs)}] {key}: {spec['version']}")
        with tempfile.TemporaryDirectory() as tmp:
            pkg = build_package(*key.split("-"), spec, Path(tmp))
            digest, size = sha256(pkg), pkg.stat().st_size
            if name in assets:
                gh.delete_asset(assets[name])
            gh.upload(release, pkg, name, "application/zip")
        manifest["models"][key] = {"file": name, "size": size, "sha256": digest, "opus_version": spec["version"],
                                   "opus_url": spec["url"], "target_label": spec.get("target_label")}
        log(f"  published {size / 2**20:.0f} MB sha256 {digest[:16]}...")
        publish_manifest()
    publish_manifest()
    log(f"done: {len(manifest['models'])} models in {args.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
