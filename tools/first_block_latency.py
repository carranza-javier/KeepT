"""First block latency per language pair (model loaded, one block per call like the app).
    python tools/first_block_latency.py de-es es-de en-es
"""
import statistics
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keept.translate.translator import Translator, route  # noqa: E402

BLOCKS = {
    "de": ["Datenschutzeinstellungen", "Alle akzeptieren",
           "Wir verwenden Cookies, um Inhalte zu personalisieren und die Zugriffe auf unsere Website zu analysieren.",
           "Melden Sie sich an, um auf Ihre Dateien zuzugreifen."],
    "en": ["Release notes", "Restart now",
           "This update improves battery life and fixes a crash that happened when opening large files.",
           "Sign in to access your files."],
    "es": ["Configuración de la cuenta", "Guardar cambios",
           "No se pudo guardar el archivo. Comprueba que tienes espacio suficiente en el disco.",
           "Inicia sesión para acceder a tus archivos."],
}

tr = Translator()
for pair in sys.argv[1:]:
    src, tgt = pair.split("-")
    t0 = time.perf_counter()
    tr.prepare(src, tgt)
    load = time.perf_counter() - t0
    tr.translate(["Warm up."], src, tgt)
    times = []
    for _ in range(3):
        for text in BLOCKS[src]:
            tr.clear_cache()
            t = time.perf_counter()
            out = tr.translate([text], src, tgt)[0]
            times.append((time.perf_counter() - t) * 1000)
    via = " via en" if len(route(src, tgt)) == 2 else ""
    print(f"{pair}{via}: first block median {statistics.median(times):.0f} ms, max {max(times):.0f} ms, "
          f"load {load * 1000:.0f} ms | {out}")
