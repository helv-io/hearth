"""Read and write a paired iPhone or iPad, over a cable or Wi-Fi. No pairing secrets are logged."""

from __future__ import annotations

import asyncio
import json
import plistlib
from datetime import datetime
from pathlib import Path

from hearth import drivers, icons, wireless
from hearth.layout import ident, is_widget, kind_of, label, monogram
from hearth.paths import version_dir
from hearth.screens import Screen, note_fields

# Present on an icon read from the device, and not part of where anything sits.
_NOT_LAYOUT = frozenset({
    "iconModDate",
    "bundleVersion",
    "allowsSuggestions",
    "allowsExternalSuggestions",
})


def friendly(exc: BaseException) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    lowered = text.lower()
    if "usbmux" in lowered or "no device" in lowered or "device not found" in lowered or "connection refused" in lowered:
        report = drivers.status()
        if report.needed and not report.ready:
            return report.detail
        return "No iPhone or iPad is connected. Unlock it and tap Trust if this computer asks."
    return text


def save_version(state, reason: str, device: str = "", screen: Screen | None = None) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = version_dir() / f"{stamp}-{reason}.plist"
    path.write_bytes(plistlib.dumps(state, fmt=plistlib.FMT_BINARY))
    payload = {"reason": reason, "device": device, "saved": stamp}
    if screen is not None:
        payload["screen"] = note_fields(screen)
    note = version_dir() / f"{stamp}-{reason}.json"
    note.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def layout_key(state) -> str:
    """Stable identity of a layout. Timestamps and app versions are not part of it."""
    return json.dumps(_layout_body(state), sort_keys=True, separators=(",", ":"), default=str)


def _layout_body(value):
    if isinstance(value, dict):
        return {key: _layout_body(item) for key, item in value.items() if key not in _NOT_LAYOUT}
    if isinstance(value, list):
        return [_layout_body(item) for item in value]
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    return value


def collapse_versions(root: Path | None = None) -> None:
    """Drop a version when it matches the neighbor kept before it. The earliest stays.

    Open and a new read both rebuild the list, so both pass through here.
    A layout that comes back after a different one is a new run and stays.
    """
    folder = version_dir() if root is None else root
    paths = sorted(folder.glob("*.plist"), key=lambda item: (item.stat().st_mtime_ns, item.name))
    kept = None
    for path in paths:
        try:
            key = layout_key(plistlib.loads(path.read_bytes()))
        except (OSError, plistlib.InvalidFileException, ValueError, TypeError):
            kept = None
            continue
        if kept is not None and key == kept:
            try:
                path.unlink()
                path.with_suffix(".json").unlink(missing_ok=True)
            except OSError:
                pass
            continue
        kept = key


# What each saved version is called in the list. Versions saved by 0.3.0 and
# earlier carry the old names in their file name, so those stay readable.
_VERSION_NAMES = {
    "read": "Read from Device",
    "pull": "Read from Device",
    "sent": "Sent to Device",
    "pushed": "Sent to Device",
    "before-send": "Before send",
    "before-push": "Before send",
}


def version_name(reason: str) -> str:
    return _VERSION_NAMES.get(reason, reason.replace("-", " "))


def list_versions() -> list[dict]:
    collapse_versions()
    rows = []
    for path in sorted(version_dir().glob("*.plist"), key=lambda item: item.stat().st_mtime, reverse=True):
        stamp = datetime.fromtimestamp(path.stat().st_mtime)
        reason = path.stem.split("-", 2)[-1] if path.stem.count("-") >= 2 else "saved"
        rows.append({
            "path": str(path),
            "label": stamp.strftime("%b %d %H:%M") + "  " + version_name(reason),
        })
    return rows[:40]


def load_version(path: str):
    return plistlib.loads(Path(path).read_bytes())


def load_note(path: str) -> dict:
    note = Path(path).with_suffix(".json")
    if not note.is_file():
        return {}
    try:
        data = json.loads(note.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    return data if isinstance(data, dict) else {}


def scan(fresh: bool = False) -> list[wireless.Candidate]:
    """Every device that can be reached right now. A failure is an empty list."""
    try:
        return asyncio.run(wireless.discover(fresh=fresh))
    except Exception:
        return []


async def _connect(chosen: wireless.Candidate | None):
    """Open the chosen device. With none chosen, take the one a person would: the last used, else the first."""
    if chosen is None:
        found = await wireless.discover()
        if not found:
            raise RuntimeError("No device is connected")
        wanted = wireless.pick(found, wireless.last_device())
        chosen = next(item for item in found if item.id == wanted)
    return await wireless.connect(chosen)


async def _work(coro):
    """Run phone work. A dropped connection says so in plain words."""
    try:
        return await coro
    except Exception as exc:
        if wireless.dropped(exc) and not isinstance(exc, wireless.CantFind):
            raise wireless.Lost() from exc
        raise


async def pull(chosen, cancel, on_state, on_icon, on_progress) -> dict:
    return await _work(_pull(chosen, cancel, on_state, on_icon, on_progress))


async def _pull(chosen, cancel, on_state, on_icon, on_progress) -> dict:
    """Read the layout, then icons. Wallpaper is a separate service call.

    getHomeScreenWallpaperPNGData terminates the SpringBoard connection on
    this phone. Icon fetches have to finish on their own connection first.
    """
    from pymobiledevice3.services.springboard import SpringBoardServicesService

    client = await _connect(chosen)
    try:
        async with wireless.Heartbeat(client):
            values = client.all_values
            product = str(values.get("ProductType") or "")
            device_class = str(values.get("DeviceClass") or "")
            ipad = device_class.lower() == "ipad" or product.startswith("iPad")
            name = values.get("DeviceName") or ("iPad" if ipad else "iPhone")
            model = client.display_name or product
            ios = values.get("ProductVersion") or ""
            wallpaper = await _wallpaper(client, SpringBoardServicesService)
            holder = _Springboard(client, SpringBoardServicesService)
            try:
                state = await holder.current.get_icon_state()
                on_state({
                    "state": state,
                    "name": name,
                    "model": model,
                    "ios": str(ios),
                    "product": product,
                    "deviceClass": device_class,
                    "wallpaper": wallpaper,
                })
                jobs = _icon_jobs(state)
                phone, pending = await _phone_icons(holder, jobs, cancel, on_icon, on_progress)
            finally:
                await holder.close()
    finally:
        await client.close()

    store = 0
    misses: list[dict] = []
    for index, job in enumerate(pending, start=1):
        if cancel.is_set():
            break
        data = None
        if job["kind"] != "shortcut":
            for candidate in job["candidates"]:
                data = await asyncio.to_thread(icons.itunes_icon, candidate)
                if data:
                    break
        if data:
            on_icon(job["ident"], icons.write_bytes(job["ident"], data, "store"))
            store += 1
        else:
            cached = icons.cached(job["ident"])
            if cached:
                on_icon(job["ident"], cached)
            else:
                misses.append(job)
        on_progress(f"Artwork {index} of {len(pending)}")
    return {"misses": misses, "phone": phone, "store": store}


class _Springboard:
    def __init__(self, client, service_type):
        self.client = client
        self.service_type = service_type
        self.current = service_type(client)

    async def close(self) -> None:
        try:
            await self.current.close()
        except Exception:
            pass

    async def reopen(self) -> None:
        await self.close()
        self.current = self.service_type(self.client)


async def _phone_icons(holder: _Springboard, jobs, cancel, on_icon, on_progress) -> tuple[int, list[dict]]:
    phone = 0
    pending: list[dict] = []
    for index, job in enumerate(jobs, start=1):
        if cancel.is_set():
            break
        cached = icons.cached(job["ident"])
        if cached and ".phone." in cached.split("#", 1)[0]:
            on_icon(job["ident"], cached)
        data = await _icon_from_phone(holder, job["candidates"])
        if data:
            on_icon(job["ident"], icons.write_bytes(job["ident"], data, "phone"))
            phone += 1
        else:
            pending.append(job)
        on_progress(f"Icons {index} of {len(jobs)}")
    return phone, pending


async def _wallpaper(client, service_type) -> str:
    try:
        async with service_type(client) as springboard:
            data = await springboard.get_wallpaper_pngdata() or b""
    except Exception:
        return ""
    if data and len(data) > 64:
        return icons.write_wallpaper(data)
    return ""


async def push(chosen, state) -> dict:
    return await _work(_push(chosen, state))


async def _push(chosen, state) -> dict:
    from pymobiledevice3.services.springboard import SpringBoardServicesService

    from hearth.layout import idents

    client = await _connect(chosen)
    try:
        async with wireless.Heartbeat(client), SpringBoardServicesService(client) as springboard:
            previous = await springboard.get_icon_state()
            await springboard.set_icon_state(state)
            await asyncio.sleep(2.0)
            readback = await springboard.get_icon_state()
            if not _acceptable(state, readback, idents):
                await springboard.set_icon_state(previous)
                await asyncio.sleep(1.0)
                raise RuntimeError("The phone did not keep that layout, so the previous one was restored.")
            return {"state": readback, "previous": previous}
    finally:
        await client.close()


def _acceptable(sent, got, idents) -> bool:
    if not isinstance(got, list) or not got or not isinstance(got[0], list):
        return False
    if sorted(idents(sent)) != sorted(idents(got)):
        return False
    if len(got) != len(sent):
        return False
    sent_dock = [ident(item) for item in sent[0]]
    got_dock = [ident(item) for item in got[0]]
    return sent_dock == got_dock


def _icon_jobs(state) -> list[dict]:
    jobs = []
    seen = set()
    for page in state:
        for item in page:
            icons_in = []
            if isinstance(item, dict) and item.get("listType") == "folder" and item.get("elementType") != "widget":
                for folder_page in item.get("iconLists") or []:
                    icons_in.extend(icon for icon in folder_page if isinstance(icon, dict))
            elif isinstance(item, dict):
                icons_in.append(item)
            for icon in icons_in:
                key = ident(icon)
                if not key or key in seen:
                    continue
                seen.add(key)
                candidates = [key]
                if is_widget(icon):
                    # The widget extension's own PNG is a blank tile. The app icon is the one to show.
                    container = str(icon.get("containerBundleIdentifier") or "")
                    candidates = [item for item in (container, key) if item]
                jobs.append({
                    "ident": key,
                    "kind": kind_of(icon),
                    "letter": monogram(label(icon)),
                    "candidates": candidates,
                })
    return jobs


def restore_icons(state) -> tuple[dict[str, str], list[dict]]:
    """Icons already on disk for a layout opened with no device attached.

    Returns the artwork found by identifier, and the jobs that have none.
    """
    found: dict[str, str] = {}
    missing: list[dict] = []
    for job in _icon_jobs(state):
        url = icons.cached(job["ident"])
        if url:
            found[job["ident"]] = url
        else:
            missing.append(job)
    return found, missing


def _connection_dead(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    return "terminat" in name or "closed" in text or "broken pipe" in text or "reset" in text


async def _icon_from_phone(holder: _Springboard, candidates: list[str]) -> bytes | None:
    """One retry with a fresh SpringBoard service if the socket dies mid-fetch."""
    for attempt in (1, 2):
        try:
            return await _icon_once(holder.current, candidates)
        except Exception as exc:
            if attempt == 2 or not _connection_dead(exc):
                return None
            await holder.reopen()
    return None


async def _icon_once(springboard, candidates: list[str]) -> bytes | None:
    for candidate in candidates:
        if not candidate:
            continue
        try:
            data = await springboard.get_icon_pngdata(candidate)
        except Exception as exc:
            if _connection_dead(exc):
                raise
            continue
        if isinstance(data, (bytes, bytearray)) and len(data) > 64:
            return bytes(data)
    return None
