# Credits and licenses

[Back to the README](../README.md)

KeepT stands on the shoulders of some excellent open work. Thank you all.

The same credits are shown in the tray menu under "About KeepT", and the full license texts ship in the program's `licenses` folder (`packaging/licenses` in the source tree). KeepT downloads its translation models on first use, so none are bundled in the installer. The text line recognizer is bundled.

## Translation models

**OPUS-MT** (Tatoeba-MT and OPUS-MT releases) is used for every language pair. It was created by Jörg Tiedemann, Santhosh Thottingal et al. at the Language Technology Research Group, University of Helsinki, and is described in "OPUS-MT: Building open translation services for the World" (EAMT 2020) and "The Tatoeba Translation Challenge" (WMT 2020). License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The models were modified: they are converted to CTranslate2 (int8) and published in the [models-v1 release](https://github.com/carranza-javier/KeepT/releases/tag/models-v1) together with the original LICENSE and README and a NOTICE describing the conversion. The model used for each pair is listed in `keept/translate/catalog.json` (built by `tools/build_model_catalog.py`).

## Text recognition model

**PP-OCRv5 latin text line recognizer** (`keept/ocr/latin_PP-OCRv5_rec_mobile.onnx`) by the PaddlePaddle Authors ([PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)), in the ONNX export published by [RapidOCR](https://github.com/RapidAI/RapidOCR). License: Apache-2.0. Unmodified.

## Data

The names of Swiss municipalities that KeepT keeps unchanged (`keept/translate/swiss_places.txt`, built by `tools/build_swiss_places.py`) come from the [Official commune register of Switzerland](https://www.agvchapp.bfs.admin.ch) of the Swiss Federal Statistical Office (BFS/OFS), open data that may be used freely with the source named.

## Libraries bundled in the Windows build

| Component | License |
| --- | --- |
| Qt 6 / PySide6 (dynamically linked, replaceable DLLs) | LGPL-3.0 |
| ONNX Runtime (Microsoft) | MIT |
| CTranslate2 (SYSTRAN, OpenNMT) | MIT |
| Intel oneMKL and OpenMP runtime, bundled with CTranslate2 | Intel Simplified Software License |
| SentencePiece (Google) | Apache-2.0 |
| sacremoses | MIT |
| py3langid (Adrien Barbaresi, based on langid.py by Marco Lui and Timothy Baldwin) | BSD-3-Clause |
| NumPy | BSD-3-Clause |
| python-mss | MIT |
| PyWinRT | MIT |
| PyYAML, joblib, regex, click, tqdm, protobuf, flatbuffers | MIT, BSD-3-Clause, Apache-2.0, MPL-2.0 |
| Python | PSF License |
| PyInstaller bootloader | GPL-2.0 with bootloader exception |

## KeepT itself

KeepT is released under the MIT License (see [LICENSE](../LICENSE)), © 2026 Javier Carranza.
