"""Which models a choice of languages needs, and how much is left to download.

Shared by the tray "Languages" dialog and by tools/gen_installer_models.py, which bakes the same
routes and sizes into the installer.
"""

from __future__ import annotations

from .translator import route


def needed_pairs(target: str, sources) -> list[tuple[str, str]]:
    """Models to translate every source language into `target`, through English when needed."""
    pairs: list[tuple[str, str]] = []
    for src in sources:
        if src and src != target:
            for pair in route(src, target):
                if pair not in pairs:
                    pairs.append(pair)
    return pairs


def package_size(store, pair: tuple[str, str]) -> int:
    """Download size of a pair from the manifest pinned in the app (0 if unknown)."""
    entry = store.manifest.get("models", {}).get(f"{pair[0]}-{pair[1]}") or {}
    return int(entry.get("size", 0))


def missing_pairs(store, target: str, sources) -> list[tuple[str, str]]:
    return [p for p in needed_pairs(target, sources) if store.get(*p) is None]


def download_bytes(store, target: str, sources) -> int:
    return sum(package_size(store, p) for p in missing_pairs(store, target, sources))


def unneeded_installed(store, target: str, sources) -> list[tuple[str, str]]:
    """Installed models that the chosen languages no longer use."""
    keep = set(needed_pairs(target, sources))
    return [(m.src, m.tgt) for m in store.installed() if (m.src, m.tgt) not in keep]
