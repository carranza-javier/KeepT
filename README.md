# KeepT

**Translate any text on your Windows screen with one shortcut.** KeepT freezes the screen,
reads the text locally and paints the translation right on top of the original, in the same
place, with the same colours and size, like a lens. No windows to copy text into, no accounts,
no API keys, and nothing leaves your PC.

![KeepT: press the shortcut, circle a paragraph, the translation appears in place](docs/keept-demo.gif)

## Download

**[Download the latest KeepT for Windows](https://github.com/carranza-javier/KeepT/releases/latest)**
(`KeepT-Setup-x.y.z.exe`, about 50 MB, Windows 10 or 11, 64-bit).

- The installer is per user: no administrator rights are needed. It can start KeepT with Windows.
- Every release lists the SHA-256 of the installer. To check it in PowerShell:
  `Get-FileHash .\KeepT-Setup-1.0.0.exe -Algorithm SHA256`
- **Windows SmartScreen:** until the code signing certificate is approved (see
  [Code signing policy](#code-signing-policy)), the installer is not signed and Windows may show
  "Windows protected your PC". Click **More info** and then **Run anyway**. The installer is built
  by GitHub Actions from this repository, and you can compare its SHA-256 with the one in the release.
- Uninstall from Settings > Apps. Downloaded models and settings are removed too.

## How to use

On the first start KeepT asks which language to translate into (you can change it any time).
Then press **`Ctrl+Alt+T`**: the monitor under the mouse freezes with a glowing border and the
text is read in the background.

| Action | Result |
| --- | --- |
| Click or tap a text block | Translate that block |
| Drag with the mouse | Translate what is inside the rectangle |
| Draw around text with a finger or a pen | Translate what is inside the lasso |
| `Enter` or "Translate screen" | Translate everything |
| Click a translated block | Copy it |
| Hold `Space`, or "Original" | Peek at the original |
| `Ctrl+C` or "Copy" | Copy all visible translations |
| Language button in the pill | Change the target language |
| `Esc`, right click, or click outside the text | Close |

The tray icon menu has the target language, the shortcut (KeepT warns if another app already
uses it), start with Windows, the update check, the downloaded models and the credits.

## Languages

German, English, Spanish, French, Italian, Portuguese, Dutch and Polish, in any direction.
KeepT uses a direct OPUS-MT model where one exists and goes through English otherwise.

No model ships with KeepT. Each one (about 80 to 250 MB) is downloaded the first time it is
needed: when you pick a target language, or the first time you translate text in a new
language. Models are kept in `%LOCALAPPDATA%\KeepT\models` and can be deleted from the tray.
After 10 minutes without use KeepT frees them from memory and reloads them in the background
as soon as you press the shortcut.

Text recognition uses the OCR built into Windows. If the OCR pack for a language is missing,
KeepT tells you how to add it (Settings > Time & language > Language).

## Privacy

Everything happens on your computer: screen captures, recognized text and translations never
leave it. There are no accounts and no telemetry. KeepT only connects to the internet to:

1. **Download translation models**, the first time a language pair is needed, from the
   [models-v1 release](https://github.com/carranza-javier/KeepT/releases/tag/models-v1) of this
   repository. Each file is verified with the SHA-256 pinned in the app and discarded if it does
   not match. Only if GitHub cannot be reached is the original model downloaded from the official
   OPUS-MT servers of the University of Helsinki and converted on your PC.
2. **Check for a new version**, at most once a day, by reading the latest release from the public
   GitHub API. Nothing about you or your screen is sent. KeepT only shows a notice with a link and
   never installs anything by itself. You can turn this off in the installer or in the tray menu.

GitHub and the University of Helsinki may log these requests (for example your IP address)
according to their own privacy policies.

## Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io), certificate by
[SignPath Foundation](https://signpath.org).

KeepT has applied for free code signing for open source projects. Until it is approved,
releases are published unsigned (see the SmartScreen note above).

- **What is signed:** only `KeepT.exe` and the `KeepT-Setup-x.y.z.exe` installer produced by the
  [Release workflow](.github/workflows/release.yml) of this repository, on GitHub-hosted
  runners, from a version tag. Nothing built on a personal computer is ever signed.
- **Team roles:**
  - Committers and reviewers: [carranza-javier](https://github.com/carranza-javier), author and
    maintainer. Changes proposed by anyone else are reviewed before they are merged.
  - Approvers: [carranza-javier](https://github.com/carranza-javier). Every signing request is
    approved manually.
- **Privacy policy:** see [Privacy](#privacy). KeepT transfers no information about the user or
  the screen. Its only network requests are the model downloads and the optional update check
  described there, which are also explained (and can be turned off) during installation.
- Third party components keep their own licenses, are listed in
  [Credits and licenses](#credits-and-licenses) and are included unsigned.

## Development

Requires Windows 10/11 and Python 3.12 or newer.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m keept --debug     # run from source
.venv\Scripts\python -m pytest            # unit tests
```

Useful tools (they work without touching the real mouse or keyboard):

- `tools/make_test_screen.py`: render a synthetic screen with known German, English and Spanish text.
- `tools/drive_overlay.py IMAGE`: drive the real overlay with synthetic input and save frames.
- `tools/ocr_dump.py IMAGE`: print the text blocks and languages KeepT detects.
- `python -m keept --selftest IMAGE|screen --target es`: run OCR and translation once and report timings (also works with the packaged `KeepT.exe`).
- `python -m keept --fake-capture IMAGE --debug-blocks`: use an image instead of the screen and outline OCR blocks.
- `tools/record_demo.py` and `tools/make_gif.py`: record the README animation from the synthetic screen.

## Releases and models

- **App releases** are built only by GitHub Actions. Pushing a tag `vX.Y.Z` that matches
  `keept/__init__.py` runs the tests, builds `KeepT.exe` with PyInstaller and the installer with
  Inno Setup on a Windows runner, and publishes them with their SHA-256 in a GitHub Release. The
  SignPath signing steps are in the same workflow and stay off until the repository variable
  `SIGNPATH_ENABLED` is `true`.
- **Translation models** live in the `models-v1` release. After changing
  `keept/translate/catalog.json` (built by `tools/build_model_catalog.py`), run the
  "Translation models" workflow from the Actions tab: `tools/publish_models.py` downloads the
  OPUS-MT originals, converts them to CTranslate2 int8 and uploads them with a `manifest.json`
  (size and SHA-256). Commit the resulting `keept/translate/models_manifest.json` so the app pins
  the new hashes.

To build locally for testing (local builds are never signed or published):

```powershell
.venv\Scripts\python tools\make_icon.py packaging\keept.ico
.venv\Scripts\pyinstaller packaging\keept.spec --noconfirm --distpath dist --workpath build
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer\keept.iss
```

## Layout

```
keept/
  app.py            entry point: tray, hotkey, per monitor overlays, preload, selftest
  engine.py         OCR and translation on worker threads, results as Qt signals
  updates.py        daily check for a newer GitHub release
  platform/         Windows specifics (hotkey, DPI, DWM cloaking, autostart) behind an interface
  capture.py        monitor capture with mss
  ocr/              Windows.Media.Ocr wrapper, block grouping, per block language re-read
  translate/        language detection, OPUS-MT catalog, model store and translator with pivot
  overlay/          overlay window, effects, pill, selection, rendering helpers
```

## Credits and licenses

KeepT downloads its translation models on first use; none are bundled in the installer.
The same credits are shown in the tray menu under "About KeepT", and the full license
texts ship in the program's `licenses` folder (`packaging/licenses` in the source tree).

Translation models

- **OPUS-MT** (Tatoeba-MT and OPUS-MT releases) for every language pair: Jörg Tiedemann,
  Santhosh Thottingal et al., Language Technology Research Group, University of Helsinki:
  "OPUS-MT: Building open translation services for the World", EAMT 2020, and
  "The Tatoeba Translation Challenge", WMT 2020.
  License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
  Modified: converted to CTranslate2 (int8) and published in the
  [models-v1 release](https://github.com/carranza-javier/KeepT/releases/tag/models-v1) with the
  original LICENSE and README and a NOTICE describing the conversion. The model used for each
  pair is listed in `keept/translate/catalog.json` (built by `tools/build_model_catalog.py`).

Libraries bundled in the Windows build

| Component | License |
| --- | --- |
| Qt 6 / PySide6 (dynamically linked, replaceable DLLs) | LGPL-3.0 |
| CTranslate2 (SYSTRAN, OpenNMT) | MIT |
| Intel oneMKL and OpenMP runtime, bundled with CTranslate2 | Intel Simplified Software License |
| SentencePiece (Google) | Apache-2.0 |
| sacremoses | MIT |
| py3langid (Adrien Barbaresi, based on langid.py by Marco Lui and Timothy Baldwin) | BSD-3-Clause |
| NumPy | BSD-3-Clause |
| python-mss | MIT |
| PyWinRT | MIT |
| PyYAML, joblib, regex, click, tqdm | MIT, BSD-3-Clause, Apache-2.0, MPL-2.0 |
| Python | PSF License |
| PyInstaller bootloader | GPL-2.0 with bootloader exception |

`tools/bench/benchmark_mt.py` compares candidate models on `tools/bench/sentences.json`.

## License

KeepT is released under the MIT License, see [LICENSE](LICENSE). Translation models and
bundled libraries keep their own licenses (see "Credits and licenses" above).
