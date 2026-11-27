"""Credits required by the licenses of the translation models and the bundled libraries.

Used by the "About KeepT" window in the tray menu; the README carries the same list.
Full license texts ship with the app in the "licenses" folder.
"""

from __future__ import annotations

from dataclasses import dataclass

CC_BY = ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/")


@dataclass(frozen=True)
class Credit:
    name: str
    role: str  # i18n key of what it is used for
    author: str
    license: str
    url: str
    note: str = ""  # i18n key of an extra note (for example "modified")


MODELS = (
    Credit("OPUS-MT (Tatoeba-MT and OPUS-MT releases), every language pair", "credit_role_all_pairs",
           "Jörg Tiedemann, Santhosh Thottingal et al., Language Technology Research Group, University of Helsinki. "
           "\"OPUS-MT: Building open translation services for the World\", EAMT 2020; "
           "\"The Tatoeba Translation Challenge\", WMT 2020.",
           CC_BY[0], "https://github.com/Helsinki-NLP/Opus-MT", "credit_note_converted"),
    Credit("PP-OCRv5 latin text line recognizer (PaddleOCR), ONNX export by RapidOCR", "credit_role_ocr",
           "PaddlePaddle Authors; RapidAI", "Apache-2.0", "https://github.com/PaddlePaddle/PaddleOCR"),
)

LIBRARIES = (
    Credit("Qt 6 / PySide6", "credit_role_ui", "The Qt Company", "LGPL-3.0", "https://www.qt.io/licensing/",
           "credit_note_lgpl"),
    Credit("ONNX Runtime", "credit_role_ocr", "Microsoft Corporation", "MIT",
           "https://github.com/microsoft/onnxruntime"),
    Credit("CTranslate2", "credit_role_engine", "SYSTRAN, OpenNMT", "MIT", "https://github.com/OpenNMT/CTranslate2"),
    Credit("Intel oneMKL, Intel OpenMP (bundled with CTranslate2)", "credit_role_engine", "Intel Corporation",
           "Intel Simplified Software License", "https://www.intel.com/content/www/us/en/developer/tools/oneapi/onemkl.html"),
    Credit("SentencePiece", "credit_role_tokens", "Google", "Apache-2.0", "https://github.com/google/sentencepiece"),
    Credit("sacremoses", "credit_role_tokens", "Alvations and contributors", "MIT", "https://pypi.org/project/sacremoses/"),
    Credit("py3langid (based on langid.py)", "credit_role_langid",
           "Adrien Barbaresi; langid.py by Marco Lui and Timothy Baldwin", "BSD-3-Clause",
           "https://github.com/adbar/py3langid"),
    Credit("NumPy", "credit_role_misc", "NumPy Developers", "BSD-3-Clause", "https://numpy.org"),
    Credit("python-mss", "credit_role_misc", "Mickaël Schoentgen", "MIT", "https://github.com/BoboTiG/python-mss"),
    Credit("PyWinRT", "credit_role_misc", "PyWinRT contributors", "MIT", "https://github.com/pywinrt/pywinrt"),
    Credit("PyYAML, joblib, regex, click, tqdm, protobuf, flatbuffers", "credit_role_misc", "Their respective authors",
           "MIT, BSD-3-Clause, Apache-2.0, MPL-2.0", "https://pypi.org"),
    Credit("Official commune register of Switzerland (list of municipality names)", "credit_role_misc",
           "Swiss Federal Statistical Office (BFS/OFS)", "Open use, source must be named",
           "https://www.agvchapp.bfs.admin.ch"),
    Credit("Python", "credit_role_misc", "Python Software Foundation", "PSF License", "https://www.python.org"),
    Credit("PyInstaller bootloader", "credit_role_misc", "PyInstaller Development Team",
           "GPL-2.0 with bootloader exception", "https://pyinstaller.org"),
)


def as_html(tr) -> str:
    """Credits as simple HTML for the About window (`tr` is i18n.tr)."""
    def items(credits):
        rows = []
        for c in credits:
            note = f"<br><i>{tr(c.note)}</i>" if c.note else ""
            lic = c.license or tr("credit_license_unstated")
            rows.append(
                f"<p style='margin:0 0 10px 0'><b>{c.name}</b>, {tr(c.role)}<br>{c.author}<br>"
                f"{tr('credit_license')}: <a href='{c.url}'>{lic}</a>{note}</p>")
        return "".join(rows)

    return (f"<h3 style='margin:0 0 6px 0'>{tr('credit_models')}</h3>{items(MODELS)}"
            f"<h3 style='margin:10px 0 6px 0'>{tr('credit_libraries')}</h3>{items(LIBRARIES)}"
            f"<p style='color:gray'>{tr('credit_full_texts')}</p>")
