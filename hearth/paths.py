"""Per-user directories. Linux uses the XDG places. Mac and Windows use the native ones.

An existing iphone-layout directory is kept, so versions saved before the
Hearth name survive. A new install uses hearth. The Darwin state path still
ends in ``versions`` before ``version_dir`` adds another, which is how the
older builds stored files.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "hearth"
LEGACY_NAME = "iphone-layout"


def _home() -> Path:
    return Path.home()


def _place(fresh: Path, legacy: Path) -> Path:
    if fresh.exists():
        return fresh
    if legacy.exists():
        return legacy
    fresh.mkdir(parents=True, exist_ok=True)
    return fresh


def config_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", _home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        root = _home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", _home() / ".config"))
    return _place(root / APP_NAME, root / LEGACY_NAME)


def state_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", _home() / "AppData" / "Local"))
        fresh, legacy = root / APP_NAME, root / LEGACY_NAME
    elif sys.platform == "darwin":
        root = _home() / "Library" / "Application Support"
        fresh = root / APP_NAME / "versions"
        legacy = root / LEGACY_NAME / "versions"
    else:
        root = Path(os.environ.get("XDG_STATE_HOME", _home() / ".local" / "state"))
        fresh, legacy = root / APP_NAME, root / LEGACY_NAME
    return _place(fresh, legacy)


def version_dir() -> Path:
    path = state_dir() / "versions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", _home() / "AppData" / "Local"))
        fresh, legacy = root / APP_NAME / "cache", root / LEGACY_NAME / "cache"
    elif sys.platform == "darwin":
        root = _home() / "Library" / "Caches"
        fresh, legacy = root / APP_NAME, root / LEGACY_NAME
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", _home() / ".cache"))
        fresh, legacy = root / APP_NAME, root / LEGACY_NAME
    return _place(fresh, legacy)


def package_dir() -> Path:
    return Path(__file__).resolve().parent


def resource_dir(name: str) -> Path:
    """A directory shipped inside the package, including a frozen build."""
    bundled = package_dir() / name
    if bundled.is_dir() and not getattr(sys, "frozen", False):
        return bundled
    if getattr(sys, "frozen", False):
        root = Path(getattr(sys, "_MEIPASS"))
        for candidate in (root / name, root / "hearth" / name):
            if candidate.is_dir():
                return candidate
    return bundled
