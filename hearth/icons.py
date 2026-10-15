"""Icon files. Phone PNGs and App Store art are written from any thread.
Generated tiles are drawn on the UI thread.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from hearth.paths import cache_dir

USER_AGENT = "iphone-layout"


def _digest(ident: str) -> str:
    return hashlib.sha256(ident.encode("utf-8")).hexdigest()[:24]


def _uri(path: Path) -> str:
    # The fragment changes when the file is rewritten, so Qt reloads it.
    return path.as_uri() + "#" + str(path.stat().st_mtime_ns)


# Phone art wins over the App Store, which wins over a generated tile.
# Older caches used a bare ".jpg" (store) or ".png" (generated).
_PREFERENCE = (
    ".phone.png",
    ".phone.jpg",
    ".store.png",
    ".store.jpg",
    ".jpg",
    ".jpeg",
    ".gen.png",
    ".png",
)


def cached(ident: str) -> str:
    root = cache_dir() / "icons"
    digest = _digest(ident)
    for suffix in _PREFERENCE:
        path = root / f"{digest}{suffix}"
        if path.is_file() and path.stat().st_size > 64:
            return _uri(path)
    return ""


def write_bytes(ident: str, data: bytes, source: str = "phone") -> str:
    root = cache_dir() / "icons"
    root.mkdir(parents=True, exist_ok=True)
    rounded = _squircle(data)
    ext = ".png" if rounded.startswith(b"\x89PNG") else ".jpg"
    path = root / f"{_digest(ident)}.{source}{ext}"
    path.write_bytes(rounded)
    return _uri(path)


def itunes_icon(bundle_id: str) -> bytes | None:
    """Exact bundle id lookup on Apple's public catalog. No name guessing."""
    if "." not in bundle_id or " " in bundle_id:
        return None
    lookup = "https://itunes.apple.com/lookup?bundleId=" + quote(bundle_id) + "&country=us"
    try:
        payload = _get_json(lookup)
    except (OSError, URLError, json.JSONDecodeError, TimeoutError):
        return None
    results = payload.get("results") if isinstance(payload, dict) else None
    if not results:
        return None
    art = results[0].get("artworkUrl512") or results[0].get("artworkUrl100")
    if not isinstance(art, str) or not art.startswith("https://"):
        return None
    art = art.replace("512x512bb", "256x256bb").replace("100x100bb", "256x256bb")
    try:
        return _get_bytes(art)
    except (OSError, URLError, TimeoutError):
        return None


def generate(ident: str, letter: str, kind: str) -> str:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

    root = cache_dir() / "icons"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{_digest(ident)}.gen.png"
    size = 180
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if kind == "shortcut":
        color = QColor("#0A84FF")
    elif kind == "widget":
        color = QColor("#2C2C2E")
    else:
        hue = int(hashlib.sha256(ident.encode()).hexdigest()[:2], 16) / 255
        color = QColor.fromHsvF(hue, 0.45, 0.55)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawRoundedRect(0, 0, size, size, 40, 40)
    painter.setPen(QPen(QColor("white")))
    font = QFont("Noto Sans")
    font.setPixelSize(68)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, (letter or "?")[:2])
    painter.end()
    image.save(str(path), "PNG")
    return _uri(path)


def write_wallpaper(data: bytes) -> str:
    path = cache_dir() / "wallpaper.png"
    path.write_bytes(data)
    return _uri(path)


def _squircle(data: bytes) -> bytes:
    """Clip artwork to a rounded square so the scene graph does not need a mask."""
    try:
        from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt
        from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
    except Exception:
        return data
    image = QImage()
    if not image.loadFromData(data):
        return data
    size = 180
    out = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    radius = size * 0.2237
    path.addRoundedRect(QRectF(1, 1, size - 2, size - 2), radius, radius)
    painter.setClipPath(path)
    painter.drawImage(QRectF(0, 0, size, size), image)
    painter.setClipping(False)
    painter.setPen(QPen(QColor(255, 255, 255, 46), 1.5))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(QRectF(1, 1, size - 2, size - 2), radius, radius)
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not out.save(buffer, "PNG"):
        return data
    return bytes(buffer.data())


def _get_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=15) as response:
        data = response.read()
    if len(data) < 64:
        raise OSError("short image")
    return data


def _get_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))
