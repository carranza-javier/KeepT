# KeepT

Translate any text on your Windows screen with one shortcut. KeepT freezes the
screen, reads the text locally and paints the translation right on top of the
original, in the same place, like a lens.

- **One click**: press `Ctrl+Alt+T`, then click a paragraph, circle some text or press `Enter` for the whole screen.
- **Local**: OCR uses the built in Windows engine and translation runs on your CPU (CTranslate2 + Argos Translate models). Screenshots never leave your PC.
- **Zero setup**: no accounts, no API keys. Lives in the system tray.
- **Languages (v1)**: German, English and Spanish, in any direction (German and Spanish pivot through English).

## Development

Requires Windows 10/11 and Python 3.12 or newer.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m keept            # run from source
.venv\Scripts\python -m pytest           # unit tests
```
