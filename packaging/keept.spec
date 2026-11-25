# PyInstaller spec for KeepT (one-folder build, starts faster than one-file).
#   .venv\Scripts\pyinstaller packaging\keept.spec --noconfirm --distpath dist --workpath build

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = Path(SPECPATH).parent

hiddenimports = (
    collect_submodules("winrt")
    + collect_submodules("keept")
    + ["sacremoses", "subword_nmt.apply_bpe", "sentencepiece", "ctranslate2",
       "ctranslate2.converters.opus_mt", "ctranslate2.converters.marian", "yaml"]
)

datas = collect_data_files("sacremoses") + collect_data_files("ctranslate2")
# License texts: our collected copies plus the ones shipped by the bundled packages.
datas += [(str(p), "licenses") for p in (ROOT / "packaging" / "licenses").glob("*.txt")]
import glob  # noqa: E402

for pattern, prefix in (("sacremoses-*.dist-info/licenses/LICENSE", "sacremoses"),
                        ("subword_nmt-*.dist-info/LICENSE", "subword-nmt"),
                        ("mss-*.dist-info/licenses/LICENSE.txt", "mss"),
                        ("numpy-*.dist-info/licenses/LICENSE.txt", "numpy"),
                        ("winrt_runtime-*.dist-info/licenses/LICENSE", "pywinrt"),
                        ("pyyaml-*.dist-info/licenses/LICENSE", "pyyaml"),
                        ("joblib-*.dist-info/licenses/LICENSE.txt", "joblib"),
                        ("regex-*.dist-info/licenses/LICENSE.txt", "regex"),
                        ("click-*.dist-info/licenses/LICENSE.txt", "click"),
                        ("tqdm-*.dist-info/licenses/LICENCE", "tqdm")):
    import sysconfig  # noqa: E402

    for f in glob.glob(str(Path(sysconfig.get_paths()["purelib"]) / pattern)):
        datas.append((f, f"licenses/{prefix}"))
binaries = collect_dynamic_libs("ctranslate2")

excludes = [
    "tkinter", "unittest", "pytest", "lib2to3", "IPython",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtPdf", "PySide6.QtWebEngineCore",
    "PySide6.QtOpenGL", "PySide6.QtSvg", "PySide6.QtDBus", "PySide6.QtSql", "PySide6.QtTest",
    "PySide6.QtMultimedia", "PySide6.QtQuickWidgets", "PySide6.QtDesigner", "PySide6.QtUiTools",
]

a = Analysis(
    [str(ROOT / "KeepT.pyw")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)

# Drop Qt translation files and unused plugins to keep the install small.
def keep(entry):
    name = entry[0].replace("\\", "/").lower()
    if "/translations/" in name:
        return False
    # Software OpenGL fallback (unused: raster widgets only) and Qt's own OpenSSL copies
    # (the Qt TLS plugin is excluded; Python's ssl module ships libcrypto-3/libssl-3).
    # cudnn64_9.dll: NVIDIA GPU library stub, unused (CPU only).
    if name.rsplit("/", 1)[-1] in ("opengl32sw.dll", "libcrypto-3-x64.dll", "libssl-3-x64.dll", "cudnn64_9.dll"):
        return False
    for plugin in ("qml", "qmltooling", "networkinformation", "tls", "generic", "iconengines/qsvgicon",
                   "imageformats/qpdf", "imageformats/qsvg", "imageformats/qtiff", "imageformats/qwebp",
                   "imageformats/qtga", "imageformats/qwbmp", "imageformats/qicns", "imageformats/qgif",
                   "imageformats/qjpeg", "platforms/qminimal", "platforms/qoffscreen", "platforms/qdirect2d"):
        if f"/plugins/{plugin}" in name:
            return False
    return True


a.binaries = [b for b in a.binaries if keep(b)]
a.datas = [d for d in a.datas if keep(d)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KeepT",
    icon=str(ROOT / "packaging" / "keept.ico"),
    console=False,
    disable_windowed_traceback=False,
    version=str(ROOT / "packaging" / "version_info.txt"),
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="KeepT")
