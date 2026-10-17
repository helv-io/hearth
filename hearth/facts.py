"""Facts the phone lists about each app, cut down to what the organizer may see.

Only the app's size, the size of its saved data, and the month it was first
obtained. The rest of the record, including the account it belongs to, is dropped
here and never leaves this function.
"""

from __future__ import annotations

import plistlib
import re
from datetime import datetime

LIMIT = 1000
_MONTH = re.compile(r"^(\d{4})-(\d{2})")
_STORE = "com.apple.iTunesStore.downloadInfo"


def _megabytes(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return 0
    return value // 2**20


def _month(blob) -> str:
    if not isinstance(blob, (bytes, bytearray)) or not blob:
        return ""
    try:
        record = plistlib.loads(bytes(blob))
        info = record.get(_STORE) if isinstance(record, dict) else None
        stamp = info.get("purchaseDate") if isinstance(info, dict) else None
    except Exception:
        return ""
    text = stamp.strftime("%Y-%m-%d") if isinstance(stamp, datetime) else str(stamp or "")
    found = _MONTH.match(text)
    if not found or not 1 <= int(found.group(2)) <= 12:
        return ""
    return f"{found.group(1)}-{found.group(2)}"


def summarize(rows) -> dict[str, dict]:
    """Rows from the phone's app list to {bundle id: {app_mb, data_mb, owned_since}}."""
    out: dict[str, dict] = {}
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = row.get("CFBundleIdentifier")
        if not isinstance(key, str) or not key:
            continue
        entry = {}
        app_mb = _megabytes(row.get("StaticDiskUsage"))
        data_mb = _megabytes(row.get("DynamicDiskUsage"))
        owned = _month(row.get("iTunesMetadata"))
        if app_mb:
            entry["app_mb"] = app_mb
        if data_mb:
            entry["data_mb"] = data_mb
        if owned:
            entry["owned_since"] = owned
        if entry:
            out[key] = entry
        if len(out) >= LIMIT:
            break
    return out
