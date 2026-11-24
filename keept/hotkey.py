"""Global hotkey: platform neutral description plus a Qt facing service."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)

MODIFIER_ORDER = ("Ctrl", "Alt", "Shift", "Win")
_ALIASES = {"control": "Ctrl", "ctrl": "Ctrl", "strg": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win", "meta": "Win"}
_NAMED_KEYS = {"space", "enter", "tab", "insert", "delete", "home", "end", "pageup", "pagedown", "pause", "printscreen"}


@dataclass(frozen=True)
class Hotkey:
    modifiers: frozenset[str]
    key: str  # "T", "5", "F8", "Space"...

    @classmethod
    def parse(cls, text: str) -> "Hotkey":
        parts = [p.strip() for p in text.replace(" ", "").split("+") if p.strip()]
        if not parts:
            raise ValueError("empty hotkey")
        mods: set[str] = set()
        for p in parts[:-1]:
            name = _ALIASES.get(p.lower())
            if name is None:
                raise ValueError(f"unknown modifier: {p}")
            mods.add(name)
        key = parts[-1]
        if len(key) == 1 and key.isascii() and key.isalnum():
            key = key.upper()
        elif key.upper().startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
            key = key.upper()
        elif key.lower() in _NAMED_KEYS:
            key = key.capitalize() if key.lower() not in ("pageup", "pagedown", "printscreen") else {
                "pageup": "PageUp", "pagedown": "PageDown", "printscreen": "PrintScreen"}[key.lower()]
        else:
            raise ValueError(f"unsupported key: {key}")
        if not mods and not key.startswith("F"):
            raise ValueError("a hotkey needs at least one modifier")
        return cls(frozenset(mods), key)

    def __str__(self) -> str:
        mods = [m for m in MODIFIER_ORDER if m in self.modifiers]
        return "+".join([*mods, self.key])

    @property
    def conflicts_with_game_bar(self) -> bool:
        return {"Win", "Alt"} <= self.modifiers


PRESETS = ("Ctrl+Alt+T", "Ctrl+Shift+T", "Ctrl+Alt+Q", "Ctrl+Shift+Space", "Alt+Q")


class HotkeyService(QObject):
    """Owns the platform backend and re-emits its events as Qt signals."""

    activated = Signal(float)  # perf_counter timestamp when the OS delivered the hotkey
    status = Signal(bool, str)  # registered ok, hotkey text

    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._started = False

    def start(self, hotkey: Hotkey) -> None:
        self._backend.start(hotkey, self.activated.emit, self.status.emit)
        self._started = True

    def set_hotkey(self, hotkey: Hotkey) -> None:
        if self._started:
            self._backend.set_hotkey(hotkey)

    def stop(self) -> None:
        if self._started:
            self._backend.stop()
            self._started = False
