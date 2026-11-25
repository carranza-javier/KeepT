"""Hold a global hotkey like another app would (to test KeepT's "already in use" handling).
    python tools/hold_hotkey.py Ctrl+Alt+T 30
"""
import ctypes
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keept.hotkey import Hotkey  # noqa: E402
from keept.platform.win32 import hotkey_to_win32  # noqa: E402

mods, vk = hotkey_to_win32(Hotkey.parse(sys.argv[1]))
ok = ctypes.windll.user32.RegisterHotKey(None, 0x77, mods, vk)
print("holding" if ok else "could not register", sys.argv[1], flush=True)
time.sleep(float(sys.argv[2]))
