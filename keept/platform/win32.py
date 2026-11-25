"""Windows implementation of the platform services (ctypes only, no pywin32)."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import sys
import threading
import time
import winreg
from pathlib import Path
from typing import Callable

from . import MonitorInfo

log = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shcore = ctypes.WinDLL("shcore")

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
WM_APP_REREGISTER = 0x8000 + 1
HOTKEY_ID = 0x4B54  # "KT"
MONITOR_DEFAULTTONEAREST = 2
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)

user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.GetMessageW.restype = wt.BOOL
user32.PeekMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT]
user32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
user32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
user32.PostThreadMessageW.argtypes = [wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.MonitorFromPoint.argtypes = [wt.POINT, wt.DWORD]
user32.MonitorFromPoint.restype = wt.HMONITOR
user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.IsWindow.argtypes = [wt.HWND]
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.BringWindowToTop.argtypes = [wt.HWND]
user32.SetFocus.argtypes = [wt.HWND]
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
shcore.GetDpiForMonitor.argtypes = [wt.HMONITOR, ctypes.c_int, ctypes.POINTER(wt.UINT), ctypes.POINTER(wt.UINT)]


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("rcMonitor", wt.RECT),
        ("rcWork", wt.RECT),
        ("dwFlags", wt.DWORD),
        ("szDevice", wt.WCHAR * 32),
    ]


user32.GetMonitorInfoW.argtypes = [wt.HMONITOR, ctypes.POINTER(MONITORINFOEXW)]

_NAMED_VK = {
    "Space": 0x20, "Enter": 0x0D, "Tab": 0x09, "Insert": 0x2D, "Delete": 0x2E, "Home": 0x24, "End": 0x23,
    "PageUp": 0x21, "PageDown": 0x22, "Pause": 0x13, "PrintScreen": 0x2C,
}
_MODS = {"Ctrl": MOD_CONTROL, "Alt": MOD_ALT, "Shift": MOD_SHIFT, "Win": MOD_WIN}


def hotkey_to_win32(hotkey) -> tuple[int, int]:
    mods = MOD_NOREPEAT
    for m in hotkey.modifiers:
        mods |= _MODS[m]
    key = hotkey.key
    if len(key) == 1:
        vk = ord(key.upper())
    elif key.startswith("F") and key[1:].isdigit():
        vk = 0x70 + int(key[1:]) - 1
    else:
        vk = _NAMED_VK[key]
    return mods, vk


class Win32HotkeyBackend:
    """RegisterHotKey on a dedicated thread that blocks in GetMessageW (no polling, no hooks)."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._tid = 0
        self._hotkey = None
        self._ready = threading.Event()
        self._on_trigger: Callable[[float], None] = lambda t: None
        self._on_status: Callable[[bool, str], None] = lambda ok, text: None

    def start(self, hotkey, on_trigger, on_status) -> None:
        self._hotkey = hotkey
        self._on_trigger = on_trigger
        self._on_status = on_status
        self._thread = threading.Thread(target=self._run, name="keept-hotkey", daemon=True)
        self._thread.start()
        self._ready.wait(2.0)

    def set_hotkey(self, hotkey) -> None:
        self._hotkey = hotkey
        if self._tid:
            user32.PostThreadMessageW(self._tid, WM_APP_REREGISTER, 0, 0)

    def stop(self) -> None:
        if self._tid:
            user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(1.0)

    def _register(self) -> None:
        user32.UnregisterHotKey(None, HOTKEY_ID)
        mods, vk = hotkey_to_win32(self._hotkey)
        ok = bool(user32.RegisterHotKey(None, HOTKEY_ID, mods, vk))
        if ok:
            log.info("Hotkey registered: %s", self._hotkey)
        else:
            log.warning("RegisterHotKey failed for %s (error %s)", self._hotkey, ctypes.get_last_error())
        self._on_status(ok, str(self._hotkey))

    def _run(self) -> None:
        self._tid = kernel32.GetCurrentThreadId()
        log.debug("Hotkey thread id %d", self._tid)
        msg = wt.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # force creation of the message queue
        self._ready.set()
        self._register()
        while True:
            r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if r == 0 or r == -1:
                break
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self._on_trigger(time.perf_counter())
            elif msg.message == WM_APP_REREGISTER:
                self._register()
        user32.UnregisterHotKey(None, HOTKEY_ID)


_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE = "KeepT"


def _autostart_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --autostart'
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    launcher = Path(__file__).resolve().parents[2] / "KeepT.pyw"
    return f'"{pythonw if pythonw.exists() else exe}" "{launcher}" --autostart'


class WindowsServices:
    def init_process(self) -> None:
        try:
            if not user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
                log.debug("DPI awareness already set (error %s)", ctypes.get_last_error())
        except AttributeError:  # pragma: no cover - very old Windows
            shcore.SetProcessDpiAwareness(2)
        try:  # own taskbar/tray identity instead of python.exe
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("KeepT")
        except Exception:  # pragma: no cover
            pass

    def monitor_at_cursor(self) -> MonitorInfo:
        pt = wt.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        user32.GetMonitorInfoW(hmon, ctypes.byref(info))
        dx, dy = wt.UINT(), wt.UINT()
        if shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(dx), ctypes.byref(dy)) != 0:
            dx.value = 96
        r = info.rcMonitor
        return MonitorInfo(info.szDevice, r.left, r.top, r.right - r.left, r.bottom - r.top, dx.value / 96.0)

    def hotkey_backend(self) -> Win32HotkeyBackend:
        return Win32HotkeyBackend()

    def hotkey_available(self, hotkey) -> bool:
        """Try to register the combination for a moment: False if another app owns it."""
        mods, vk = hotkey_to_win32(hotkey)
        probe_id = HOTKEY_ID + 1
        if user32.RegisterHotKey(None, probe_id, mods, vk):
            user32.UnregisterHotKey(None, probe_id)
            return True
        log.info("Hotkey %s is taken (error %s)", hotkey, ctypes.get_last_error())
        return False

    def system_language(self) -> str:
        langid = kernel32.GetUserDefaultUILanguage() & 0x3FF
        return {0x07: "de", 0x09: "en", 0x0A: "es"}.get(langid, "en")

    def prefers_dark(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
        except OSError:
            return False

    def autostart_enabled(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
                winreg.QueryValueEx(k, _RUN_VALUE)
                return True
        except OSError:
            return False

    def set_autostart(self, enabled: bool) -> None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
                if enabled:
                    winreg.SetValueEx(k, _RUN_VALUE, 0, winreg.REG_SZ, _autostart_command())
                else:
                    try:
                        winreg.DeleteValue(k, _RUN_VALUE)
                    except FileNotFoundError:
                        pass
        except OSError as exc:
            log.error("Could not change autostart: %s", exc)

    @staticmethod
    def _dwm_set(win_id: int, attr: int, value: int) -> bool:
        try:
            v = ctypes.c_int(value)
            return ctypes.windll.dwmapi.DwmSetWindowAttribute(wt.HWND(win_id), attr, ctypes.byref(v), ctypes.sizeof(v)) == 0
        except Exception as exc:  # noqa: BLE001
            log.debug("DwmSetWindowAttribute(%d) failed: %s", attr, exc)
            return False

    def prepare_overlay_window(self, win_id: int) -> None:
        """No DWM open/close animations (they add a fade and delay)."""
        self._dwm_set(win_id, 3, 1)  # DWMWA_TRANSITIONS_FORCEDISABLED

    def set_cloaked(self, win_id: int, cloaked: bool) -> None:
        """Hide/show a window instantly through DWM, without ShowWindow (which can stall)."""
        self._dwm_set(win_id, 13, 1 if cloaked else 0)  # DWMWA_CLOAK

    def park_window(self, win_id: int) -> None:
        """Move a window far outside every monitor so it can never get input while idle."""
        SWP_NOSIZE, SWP_NOZORDER, SWP_NOACTIVATE = 0x0001, 0x0004, 0x0010
        user32.SetWindowPos(wt.HWND(win_id), None, -32000, -32000, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)

    def foreground_window(self) -> int:
        return int(user32.GetForegroundWindow() or 0)

    def restore_foreground(self, win_id: int) -> None:
        if win_id and user32.IsWindow(wt.HWND(win_id)):
            user32.SetForegroundWindow(wt.HWND(win_id))

    def open_folder(self, path: Path) -> None:
        import os

        os.startfile(str(path))  # noqa: S606 - Explorer on our own folder

    def bring_to_front(self, win_id: int) -> None:
        hwnd = wt.HWND(win_id)
        if user32.GetForegroundWindow() == win_id:
            return
        if user32.SetForegroundWindow(hwnd) and user32.GetForegroundWindow() == win_id:
            return
        # Fallback: attach to the thread that owns the foreground window.
        fg = user32.GetForegroundWindow()
        fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        my_tid = kernel32.GetCurrentThreadId()
        attached = bool(fg_tid and fg_tid != my_tid and user32.AttachThreadInput(my_tid, fg_tid, True))
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(my_tid, fg_tid, False)
        if user32.GetForegroundWindow() != win_id:
            log.warning("Overlay could not take keyboard focus")
