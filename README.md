# KeepT

Translate any text on your Windows screen with one shortcut. KeepT freezes the
screen, reads the text locally and paints the translation right on top of the
original, in the same place and with the same colours, like a lens.

- **One click**: press `Ctrl+Alt+T`, then click a paragraph, circle some text, drag a rectangle, or press `Enter` for the whole screen.
- **Local**: OCR uses the built in Windows engine and translation runs on your CPU (CTranslate2 with Argos Translate models). Screenshots never leave your PC. The only network access is downloading a language model the first time it is needed.
- **Zero setup**: no accounts, no API keys. Lives in the system tray.
- **Languages (v1)**: German, English and Spanish in any direction (German and Spanish pivot through English).

## Using it

| Action | Result |
| --- | --- |
| `Ctrl+Alt+T` | Freeze the monitor under the mouse. Press again or `Esc` to close. |
| Click a text block | Translate that block |
| Circle text / drag a diagonal | Translate what is inside the lasso or rectangle |
| `Enter` or "Translate screen" | Translate everything |
| Click a translated block | Copy it |
| Hold `Space` | Peek at the original |
| `Ctrl+C` or "Copy" | Copy all visible translations |
| Click outside the text | Close |

The tray menu sets the target language (default: the Windows language), the
shortcut, start with Windows and lets you delete downloaded models.

Models are stored in `%LOCALAPPDATA%\KeepT\models`, settings in
`%APPDATA%\KeepT\config.json` and the log in `%LOCALAPPDATA%\KeepT\keept.log`.
Set `"low_memory": true` in the config to disable Intel MKL in CTranslate2
(much less committed memory, about 25 % slower).

If Windows lacks the OCR pack for a language, KeepT tells you once from the tray.
It can be added in Settings > Time & language > Language, or as administrator:
`Add-WindowsCapability -Online -Name "Language.OCR~~~de-DE~0.0.1.0"`.

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

## Building

```powershell
.venv\Scripts\python tools\make_icon.py packaging\keept.ico
.venv\Scripts\pyinstaller packaging\keept.spec --noconfirm --distpath dist --workpath build
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer\keept.iss
```

The installer (`installer\Output\KeepT-Setup-1.0.0.exe`) installs per user,
without administrator rights, and can start KeepT with Windows.

## Layout

```
keept/
  app.py            entry point: tray, hotkey, per monitor overlays, preload, selftest
  engine.py         OCR and translation on worker threads, results as Qt signals
  platform/         Windows specifics (hotkey, DPI, DWM cloaking, autostart) behind an interface
  capture.py        monitor capture with mss
  ocr/              Windows.Media.Ocr wrapper, block grouping, per block language re-read
  translate/        language detection, Argos model store, CTranslate2 translator with pivot
  overlay/          overlay window, effects, pill, selection, rendering helpers
```
