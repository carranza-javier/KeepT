# Development

[Back to the README](../README.md)

Want to poke around? Welcome. KeepT is Python with PySide6 (Qt) for the overlay, the Windows OCR through PyWinRT, onnxruntime for the second reading and CTranslate2 for the translation models.

## Run it from source

You need Windows 10 or 11 and Python 3.12 or newer.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m keept --debug     # run from source
.venv\Scripts\python -m pytest            # unit tests
```

## Tools for testing

These work without touching your real mouse or keyboard:

- `tools/make_test_screen.py` renders a synthetic screen with known German, English and Spanish text.
- `tools/drive_overlay.py IMAGE` drives the real overlay with synthetic input and saves frames. With `--warm de,fr --scenario timing` it measures the time to the first translated block after a click, a rectangle and Enter.
- `tools/ocr_dump.py IMAGE` prints the text blocks and languages KeepT detects.
- `tools/render_letter.py OUT.png [ZOOM]` renders the multilingual sample letter in `docs/` (used by `tests/test_letter.py`).
- `python -m keept --selftest IMAGE|screen --target es` runs OCR and translation once and reports timings. It also works with the packaged `KeepT.exe`.
- `python -m keept --fake-capture IMAGE --debug-blocks` uses an image instead of the screen and outlines the OCR blocks.
- `tools/record_demo.py` and `tools/make_gif.py` record the README animation from the synthetic screen.
- `tools/bench/benchmark_mt.py` compares candidate translation models on `tools/bench/sentences.json`.

## Releases and models

- **App releases** are built only by GitHub Actions. Pushing a tag `vX.Y.Z` that matches `keept/__init__.py` runs the tests, builds `KeepT.exe` with PyInstaller and the installer with Inno Setup on a Windows runner, and publishes them with their SHA-256 in a GitHub Release, as a pre-release while the version is 0.x. The SignPath signing steps are in the same workflow and stay off until the repository variable `SIGNPATH_ENABLED` is `true`.
- **Translation models** live in the `models-v1` release. After changing `keept/translate/catalog.json` (built by `tools/build_model_catalog.py`), run the "Translation models" workflow from the Actions tab. `tools/publish_models.py` downloads the OPUS-MT originals, converts them to CTranslate2 int8 and uploads them with a `manifest.json` that lists the size and SHA-256 of each one. Commit the resulting `keept/translate/models_manifest.json` so the app pins the new hashes, and run `tools/gen_installer_models.py` so the installer's language page uses the same packages, sizes and hashes.

To build locally for testing (local builds are never signed or published):

```powershell
.venv\Scripts\python tools\make_icon.py packaging\keept.ico
.venv\Scripts\pyinstaller packaging\keept.spec --noconfirm --distpath dist --workpath build
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer\keept.iss
```

## Where things live

```
keept/
  app.py            entry point: tray, hotkey, per monitor overlays, preload, selftest
  engine.py         OCR and translation on worker threads, results as Qt signals
  updates.py        daily check for a newer GitHub release
  platform/         Windows specifics (hotkey, DPI, DWM cloaking, autostart) behind an interface
  capture.py        monitor capture with mss
  ocr/              Windows.Media.Ocr wrapper, block grouping, second reading with PP-OCRv5 latin
  translate/        language detection, OPUS-MT catalog, model store and translator with pivot
  overlay/          overlay window, effects, pill, selection, rendering helpers
```

Everything Windows specific sits behind small interfaces in `keept/platform` and `keept/ocr`, so a Linux version can be added later without touching the overlay or the translation.
