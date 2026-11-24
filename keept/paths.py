"""Per-user data locations and logging setup."""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

from . import APP_NAME


def _env_dir(var: str, fallback: Path) -> Path:
    value = os.environ.get(var)
    return Path(value) if value else fallback


def config_dir() -> Path:
    """Roaming settings folder, e.g. %APPDATA%\\KeepT."""
    override = os.environ.get("KEEPT_CONFIG_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = _env_dir("APPDATA", Path.home() / "AppData" / "Roaming")
    else:
        base = _env_dir("XDG_CONFIG_HOME", Path.home() / ".config")
    return base / APP_NAME


def data_dir() -> Path:
    """Local (non roaming) data folder, e.g. %LOCALAPPDATA%\\KeepT."""
    if sys.platform == "win32":
        base = _env_dir("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    else:
        base = _env_dir("XDG_DATA_HOME", Path.home() / ".local" / "share")
    return base / APP_NAME


def models_dir() -> Path:
    override = os.environ.get("KEEPT_MODELS_DIR")
    return Path(override) if override else data_dir() / "models"


def resource_path(*parts: str) -> Path:
    """Path to a bundled resource, both from source and from a PyInstaller build."""
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS) / "keept"
    else:
        base = Path(__file__).resolve().parent
    return base.joinpath("resources", *parts)


def setup_logging(debug: bool = False) -> Path:
    log_dir = data_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "keept.log"
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    fmt = logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)s %(name)s: %(message)s", "%H:%M:%S")
    handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(fmt)
    root.addHandler(handler)
    if sys.stderr is not None:
        stream = logging.StreamHandler()
        stream.setFormatter(fmt)
        root.addHandler(stream)
    return log_file
