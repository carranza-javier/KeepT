"""Simulate the global hotkey by posting WM_HOTKEY to KeepT's hotkey thread (thread id from the debug log).

Useful when real key presses are not possible (locked session, remote runs).
    python tools/post_hotkey.py <thread id>
"""
import ctypes
import sys

WM_HOTKEY = 0x0312
HOTKEY_ID = 0x4B54

if __name__ == "__main__":
    ok = ctypes.windll.user32.PostThreadMessageW(int(sys.argv[1]), WM_HOTKEY, HOTKEY_ID, 0)
    print("posted" if ok else f"failed ({ctypes.GetLastError()})")
