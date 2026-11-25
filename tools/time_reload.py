"""Measure time to first translated block after the models were released.

Posts the hotkey (WM_HOTKEY to KeepT's hotkey thread) and Enter (to the overlay window)
with exact delays, waiting between rounds so KeepT releases its models again
(run KeepT with KEEPT_IDLE_RELEASE_S=15 --debug).
    python tools/time_reload.py <hotkey thread id> 0.3 0.6 1.0
"""
import ctypes
import sys
import time

user32 = ctypes.windll.user32
WM_HOTKEY, HOTKEY_ID, WM_KEYDOWN, WM_KEYUP = 0x0312, 0x4B54, 0x0100, 0x0101


def overlay_hwnds():
    found = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(hwnd, _):
        buf = ctypes.create_unicode_buffer(64)
        user32.GetWindowTextW(hwnd, buf, 64)
        if buf.value == "KeepT Overlay":
            found.append(hwnd)
        return True

    user32.EnumWindows(proc(cb), 0)
    return found


def key(vk):
    for h in overlay_hwnds():  # only the open one reacts
        user32.PostMessageW(h, WM_KEYDOWN, vk, 1)
        user32.PostMessageW(h, WM_KEYUP, vk, 0xC0000001)


tid = int(sys.argv[1])
for delay in map(float, sys.argv[2:]):
    time.sleep(22)  # let the idle timer release the models
    user32.PostThreadMessageW(tid, WM_HOTKEY, HOTKEY_ID, 0)
    time.sleep(delay)
    key(0x0D)
    time.sleep(4)
    key(0x1B)
    print("round", delay, flush=True)
