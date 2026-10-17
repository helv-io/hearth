"""Per-user directories. Linux uses the XDG places. Mac and Windows use the native ones.

Every directory is named hearth. The Darwin state path still ends in
``versions`` before ``version_dir`` adds another. Leave that alone.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "hearth"


def _home() -> Path:
    return Path.home()


def _place(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", _home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        root = _home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", _home() / ".config"))
    return _place(root / APP_NAME)


def state_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", _home() / "AppData" / "Local"))
        path = root / APP_NAME
    elif sys.platform == "darwin":
        root = _home() / "Library" / "Application Support"
        path = root / APP_NAME / "versions"
    else:
        root = Path(os.environ.get("XDG_STATE_HOME", _home() / ".local" / "state"))
        path = root / APP_NAME
    return _place(path)


def version_dir() -> Path:
    path = state_dir() / "versions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", _home() / "AppData" / "Local"))
        path = root / APP_NAME / "cache"
    elif sys.platform == "darwin":
        root = _home() / "Library" / "Caches"
        path = root / APP_NAME
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME", _home() / ".cache"))
        path = root / APP_NAME
    return _place(path)


def package_dir() -> Path:
    return Path(__file__).resolve().parent


def window_icon_path() -> Path:
    """The picture for the window and Dock icon. A Mac icon has clear space around
    the tile and transparent corners, so macOS gets its own picture."""
    name = "hearth-macos.png" if sys.platform == "darwin" else "hearth.png"
    return resource_dir("qml") / name


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
