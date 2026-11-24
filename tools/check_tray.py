"""Exercise the tray settings of a real KeepT instance (isolated config and models dirs).

    KEEPT_CONFIG_DIR=... KEEPT_MODELS_DIR=... python tools/check_tray.py out.png
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from keept.app import KeepTApp, parse_args  # noqa: E402
from keept.platform import services  # noqa: E402


def pump(ms):
    end = time.perf_counter() + ms / 1000
    while time.perf_counter() < end:
        QApplication.processEvents()
        time.sleep(0.01)


def main() -> int:
    services().init_process()
    qapp = QApplication(sys.argv[:1])
    qapp.setQuitOnLastWindowClosed(False)
    app = KeepTApp(qapp, parse_args([]))
    statuses = []
    app.hotkeys.status.connect(lambda ok, text: statuses.append((ok, text)))
    pump(500)
    plat = services()
    was_autostart = plat.autostart_enabled()
    results = {}

    app.tray.rebuild()
    menu = app.tray.menu
    results["menu"] = [a.text() for a in menu.actions() if a.text()]
    menu.adjustSize()
    menu.grab().save(sys.argv[1])
    for a in menu.actions():
        if a.menu():
            results[a.text()] = [x.text() for x in a.menu().actions() if x.text()]

    app.set_hotkey("Ctrl+Shift+Q")
    pump(400)
    results["hotkey_status"] = statuses[-1] if statuses else None
    app.set_hotkey("Ctrl+Alt+T")
    pump(400)
    results["hotkey_back"] = statuses[-1] if statuses else None

    app.set_autostart(False)
    results["autostart_off"] = plat.autostart_enabled()
    app.set_autostart(True)
    results["autostart_on"] = plat.autostart_enabled()
    app.set_autostart(was_autostart)

    app.set_target("en")
    cfg = json.loads((Path(os.environ["KEEPT_CONFIG_DIR"]) / "config.json").read_text(encoding="utf-8"))
    results["saved_target"] = cfg["target_lang"]

    store = app.engine.translator.store
    before = [f"{m.src}_{m.tgt}" for m in store.installed()]
    if before:
        src, tgt = before[0].split("_")
        app.delete_model(src, tgt)
    results["models_before"] = before
    results["models_after"] = [f"{m.src}_{m.tgt}" for m in store.installed()]
    print(json.dumps(results, ensure_ascii=False, indent=1))
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
