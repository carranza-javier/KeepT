"""Update check: at most once a day, ask the GitHub API for the newest KeepT release.

While KeepT is 0.x every release is a pre-release, so the check reads the release list (which
includes pre-releases) instead of "latest" (which skips them), and takes the highest vX.Y.Z
tag. Drafts and other tags (such as the models-v1 release) are ignored.

Only the public release information is requested (no identifiers are sent). When a newer
version exists, the tray shows a notice with a link to the download page; KeepT never
downloads or installs updates by itself. Can be turned off in the tray menu.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import urllib.request
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from . import __version__

log = logging.getLogger(__name__)

REPO = "carranza-javier/KeepT"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
CHECK_EVERY_S = 24 * 3600


def parse_version(tag: str) -> tuple[int, int, int] | None:
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (tag or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def is_newer(tag: str, current: str = __version__) -> bool:
    new, cur = parse_version(tag), parse_version(current)
    return bool(new and cur and new > cur)


@dataclass
class Release:
    version: str
    page_url: str
    installer_url: str


def fetch_latest(opener=None) -> Release | None:
    """The newest published app release, pre-releases included, or None if there is none."""
    req = urllib.request.Request(RELEASES_API, headers={"Accept": "application/vnd.github+json",
                                                        "User-Agent": "KeepT-update-check"})
    with (opener or urllib.request.urlopen)(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    candidates = [r for r in data if isinstance(r, dict) and not r.get("draft") and parse_version(r.get("tag_name", ""))]
    if not candidates:
        return None
    newest = max(candidates, key=lambda r: parse_version(r["tag_name"]))
    installer = next((a["browser_download_url"] for a in newest.get("assets", [])
                      if a.get("name", "").lower().endswith(".exe")), "")
    return Release(newest["tag_name"].lstrip("v"), newest.get("html_url") or RELEASES_PAGE, installer)


class UpdateChecker(QObject):
    update_available = Signal(object)  # Release

    def __init__(self, config, save, opener=None, parent=None):
        super().__init__(parent)
        self.config = config
        self._save = save
        self._opener = opener
        self._running = False
        self.available: Release | None = None

    def due(self) -> bool:
        return bool(self.config.check_updates) and time.time() - float(self.config.last_update_check or 0) >= CHECK_EVERY_S

    def check_if_due(self) -> None:
        if self._running or not self.due():
            return
        self._running = True
        threading.Thread(target=self._run, name="keept-update-check", daemon=True).start()

    def _run(self) -> None:
        try:
            release = fetch_latest(self._opener)
            self.config.last_update_check = time.time()
            self._save()
            if release and is_newer(release.version):
                log.info("KeepT %s is available (running %s)", release.version, __version__)
                self.available = release
                self.update_available.emit(release)
            else:
                log.info("No newer KeepT release (running %s)", __version__)
        except Exception as exc:  # noqa: BLE001 - offline or GitHub down: try again next time
            log.info("Update check failed: %s", exc)
        finally:
            self._running = False
