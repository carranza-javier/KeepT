"""Real keyboard/mouse input and screenshots for end to end tests on the live desktop.

Safety: keys and clicks (other than the global hotkey) are only sent when the
foreground window belongs to a KeepT process, so nothing lands in other apps.

    python tools/real_input.py hotkey
    python tools/real_input.py key Return|Escape|Space
    python tools/real_input.py click X Y            (physical virtual-screen coords)
    python tools/real_input.py clickat X Y          (click a KeepT window that has no focus)
    python tools/real_input.py drag X1 Y1 X2 Y2 ... (polyline)
    python tools/real_input.py shot out.png [monitor index, 0 = all]
    python tools/real_input.py fg
"""

import ctypes
import ctypes.wintypes as wt
import sys
import time

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_KEYUP = 0x2
MOUSEEVENTF_MOVE, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x1, 0x2, 0x4
MOUSEEVENTF_ABSOLUTE, MOUSEEVENTF_VIRTUALDESK = 0x8000, 0x4000
VK = {"Return": 0x0D, "Escape": 0x1B, "Space": 0x20, "Ctrl": 0x11, "Alt": 0x12, "T": 0x54}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _U)]


def _send(*inputs):
    arr = (INPUT * len(inputs))(*inputs)
    user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def key_input(vk, up=False):
    i = INPUT(INPUT_KEYBOARD)
    i.u.ki = KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, 0)
    return i


def foreground_is_keept() -> bool:
    import subprocess

    hwnd = user32.GetForegroundWindow()
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid.value}", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
    name = out.split(",")[0].strip('"').lower() if out.strip() else ""
    return name in ("keept.exe", "python.exe", "pythonw.exe") and _title(hwnd).startswith("KeepT")


def _title(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def require_keept():
    if not foreground_is_keept():
        print("refused: foreground window is not KeepT:", _title(user32.GetForegroundWindow()))
        raise SystemExit(2)


def move_abs(x, y, flags=0):
    vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
    i = INPUT(INPUT_MOUSE)
    i.u.mi = MOUSEINPUT(int((x - vx) * 65535 / (vw - 1)), int((y - vy) * 65535 / (vh - 1)), 0,
                        MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | flags, 0, 0)
    _send(i)


def main():
    cmd = sys.argv[1]
    if cmd == "hotkey":
        _send(key_input(VK["Ctrl"]), key_input(VK["Alt"]), key_input(VK["T"]),
              key_input(VK["T"], True), key_input(VK["Alt"], True), key_input(VK["Ctrl"], True))
    elif cmd == "key":
        require_keept()
        vk = VK[sys.argv[2]]
        _send(key_input(vk))
        if len(sys.argv) < 4 or sys.argv[3] != "hold":
            _send(key_input(vk, True))
    elif cmd == "keyup":
        _send(key_input(VK[sys.argv[2]], True))
    elif cmd == "click":
        require_keept()
        x, y = float(sys.argv[2]), float(sys.argv[3])
        move_abs(x, y)
        time.sleep(0.05)
        move_abs(x, y, MOUSEEVENTF_LEFTDOWN)
        time.sleep(0.05)
        move_abs(x, y, MOUSEEVENTF_LEFTUP)
    elif cmd == "clickat":
        # For windows that never take focus: require the window under the cursor to be KeepT's.
        x, y = float(sys.argv[2]), float(sys.argv[3])
        move_abs(x, y)
        time.sleep(0.1)
        pt = wt.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.WindowFromPoint.restype = wt.HWND
        hwnd = user32.GetAncestor(user32.WindowFromPoint(pt), 2)
        if not _title(hwnd).startswith("KeepT"):
            print("refused: window under cursor is not KeepT:", _title(hwnd))
            raise SystemExit(2)
        move_abs(x, y, MOUSEEVENTF_LEFTDOWN)
        time.sleep(0.05)
        move_abs(x, y, MOUSEEVENTF_LEFTUP)
    elif cmd == "drag":
        require_keept()
        pts = list(map(float, sys.argv[2:]))
        pts = list(zip(pts[::2], pts[1::2]))
        move_abs(*pts[0])
        time.sleep(0.05)
        move_abs(*pts[0], MOUSEEVENTF_LEFTDOWN)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            for k in range(1, 9):
                move_abs(x0 + (x1 - x0) * k / 8, y0 + (y1 - y0) * k / 8)
                time.sleep(0.008)
        move_abs(*pts[-1], MOUSEEVENTF_LEFTUP)
    elif cmd == "move":
        move_abs(float(sys.argv[2]), float(sys.argv[3]))
    elif cmd == "shot":
        import mss
        import mss.tools

        idx = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        with mss.MSS() as s:
            img = s.grab(s.monitors[idx])
            mss.tools.to_png(img.rgb, img.size, output=sys.argv[2])
    elif cmd == "fg":
        print(_title(user32.GetForegroundWindow()), foreground_is_keept())


if __name__ == "__main__":
    main()
