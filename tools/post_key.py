"""Post a key press to the KeepT overlay window (Return, Escape, Space...), like a real key.

    python tools/post_key.py Return
"""
import ctypes
import sys

VK = {"Return": 0x0D, "Escape": 0x1B, "Space": 0x20}
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101

if __name__ == "__main__":
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, "KeepT Overlay")
    if not hwnd:
        print("overlay window not found")
        raise SystemExit(1)
    vk = VK[sys.argv[1]]
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, 1)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, 0xC0000001)
    print("posted", sys.argv[1])
