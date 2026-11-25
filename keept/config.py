"""User configuration stored as JSON in %APPDATA%\\KeepT\\config.json."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .paths import config_dir

log = logging.getLogger(__name__)

from .languages import CODES as SUPPORTED_LANGS  # noqa: E402

OLD_DEFAULT_HOTKEY = "Ctrl+Alt+T"  # default up to 1.0.0


@dataclass
class Config:
    hotkey: str = "F1"
    hotkey_chosen: bool = False  # the user picked the shortcut (otherwise it follows the default)
    target_lang: str = ""  # empty means "use the Windows language"
    autostart: bool = True
    last_source_lang: str = "en"
    ocr_warning_shown: bool = False
    first_run_done: bool = False
    target_chosen: bool = False  # the first run language question was answered
    debug_blocks: bool = False
    # Disables MKL weight pre-packing in CTranslate2: committed memory drops from 2-3.3 GB to
    # ~0.6 GB, translation gets ~20 % slower. RAM in Task Manager is the same either way.
    low_memory: bool = False
    ocr_warned: list = None  # languages whose missing OCR pack was already reported
    check_updates: bool = True  # ask GitHub for a newer release, at most once a day
    last_update_check: float = 0.0

    def __post_init__(self):
        if self.ocr_warned is None:
            self.ocr_warned = []

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or default_path()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError) as exc:
            log.warning("Config unreadable (%s), using defaults", exc)
            return cls()
        if not isinstance(raw, dict):
            return cls()
        known = {f.name for f in fields(cls)}
        cfg = cls(**{k: v for k, v in raw.items() if k in known})
        if cfg.target_lang and cfg.target_lang not in SUPPORTED_LANGS:
            cfg.target_lang = ""
        if cfg.last_source_lang not in SUPPORTED_LANGS:
            cfg.last_source_lang = "en"
        if not cfg.hotkey_chosen and cfg.hotkey == OLD_DEFAULT_HOTKEY:
            cfg.hotkey = cls.hotkey  # 1.0.0 saved its default; move to the new default once
        return cfg

    def save(self, path: Path | None = None) -> None:
        path = path or default_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            log.error("Could not save config: %s", exc)

    def effective_target(self, system_lang: str) -> str:
        if self.target_lang in SUPPORTED_LANGS:
            return self.target_lang
        return system_lang if system_lang in SUPPORTED_LANGS else "en"


def default_path() -> Path:
    return config_dir() / "config.json"
