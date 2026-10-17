"""Every way to reach an iPhone or iPad, in one place: cable first, then Wi-Fi.

`discover` lists what can be reached, one row per device. `connect` opens one.
`Heartbeat` keeps a Wi-Fi connection alive. Pairing happens over the cable only,
so a phone that was never plugged in never shows up here.

The pairing record is a secret. It is copied into a folder only the person can
read, and it is never logged or printed.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from hearth.paths import config_dir, state_dir

CANT_FIND = "Can't find your iPhone on this network. Wake it, or plug it in."
LOST = "Lost the connection to your iPhone. Wake it and try again."
WIFI_LABEL = "Connect over Wi-Fi"
WIFI_HINT = "Lets Hearth find your paired iPhone on your home network."

# Looking on the network costs a few seconds, so a fresh answer is reused for a short while.
BROWSE_SECONDS = 2.0
BROWSE_KEEP = 8.0

_names: dict[str, str] = {}
_browsed: dict = {"at": 0.0, "found": []}


class CantFind(RuntimeError):
    """The phone did not answer on the network."""

    def __init__(self):
        super().__init__(CANT_FIND)


class Lost(RuntimeError):
    """The connection dropped partway through."""

    def __init__(self):
        super().__init__(LOST)


@dataclass(frozen=True)
class Candidate:
    udid: str
    name: str
    transport: str  # "USB" or "Wi-Fi"
    address: str = ""  # set when found by name on the network
    serial: str = ""  # set when the computer's USB service knows it
    record: dict | None = field(default=None, repr=False, compare=False)

    @property
    def id(self) -> str:
        return key(self.udid)

    @property
    def label(self) -> str:
        name = self.name or "iPhone"
        return name if self.transport == "USB" else f"{name} (Wi-Fi)"


def key(udid: str) -> str:
    """The same phone is written with and without a dash depending on who reports it."""
    return (udid or "").replace("-", "").upper()


# --- what is remembered -------------------------------------------------


def _path() -> Path:
    return config_dir() / "devices.json"


def _stored() -> dict:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _store(**values) -> None:
    data = _stored()
    data.update(values)
    try:
        _path().write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def wifi_enabled() -> bool:
    value = _stored().get("wifi_enabled")
    return value if isinstance(value, bool) else True


def set_wifi_enabled(enabled: bool) -> None:
    _store(wifi_enabled=bool(enabled))


def last_device() -> str:
    value = _stored().get("last_device")
    return value if isinstance(value, str) else ""


def remember(udid: str) -> None:
    if udid and last_device() != udid:
        _store(last_device=udid)


def pairing_dir() -> Path:
    path = state_dir() / "pairing"
    path.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        os.chmod(path, 0o700)
    return path


def stored_records() -> list[Path]:
    try:
        return sorted(pairing_dir().glob("*.plist"))
    except OSError:
        return []


def keep_pair_record(udid: str, record) -> None:
    """Copy the pairing record where a wireless connection can find it, readable only by this person."""
    import plistlib

    if not udid or not isinstance(record, dict) or "HostID" not in record:
        return
    target = pairing_dir() / f"{key(udid)}.plist"
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(target, flags, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(plistlib.dumps(record))
        os.chmod(target, 0o600)
    except OSError:
        pass
    # pymobiledevice3 saves its own copy beside ours when it pairs. Close that one too.
    for other in stored_records():
        with contextlib.suppress(OSError):
            os.chmod(other, 0o600)


# --- finding devices ----------------------------------------------------


def dedupe(found: list[Candidate]) -> list[Candidate]:
    """One row per phone. A cable beats the network. The USB service beats a name found on the network."""
    def rank(item: Candidate) -> int:
        if item.transport == "USB":
            return 0
        return 1 if item.serial else 2

    best: dict[str, Candidate] = {}
    for item in found:
        old = best.get(item.id)
        if old is None or rank(item) < rank(old):
            best[item.id] = item
    return sorted(best.values(), key=lambda item: (item.transport != "USB", item.label.lower()))


def pick(found: list[Candidate], remembered: str = "", current: str = "") -> str:
    """Which device to operate. The one in use stays. Then the last one chosen. Then the first."""
    ids = [item.id for item in found]
    for wanted in (key(current), key(remembered)):
        if wanted and wanted in ids:
            return wanted
    return ids[0] if ids else ""


def labels(found: list[Candidate]) -> list[str]:
    """What the drop-down shows. Two phones with the same name get a number."""
    seen: dict[str, int] = {}
    out = []
    for item in found:
        count = seen.get(item.label, 0) + 1
        seen[item.label] = count
        out.append(item.label if count == 1 else f"{item.label} {count}")
    return out


async def _usbmux(wifi: bool) -> list[Candidate]:
    try:
        from pymobiledevice3.usbmux import list_devices

        listed = await list_devices()
    except Exception:
        return []  # no USB service is fine: the network can still work
    out = []
    for item in listed or []:
        if item.is_usb:
            out.append(Candidate(item.serial, "", "USB", serial=item.serial))
        elif wifi:
            out.append(Candidate(item.serial, "", "Wi-Fi", serial=item.serial))
    return out


async def _browse(folder: Path | None, timeout: float) -> list[Candidate]:
    out: list[Candidate] = []
    try:
        from pymobiledevice3.lockdown import get_mobdev2_lockdowns

        async for address, lockdown in get_mobdev2_lockdowns(only_paired=True, pair_records=folder, timeout=timeout):
            try:
                name = str(await lockdown.get_value(key="DeviceName") or "")
                out.append(Candidate(lockdown.udid, name, "Wi-Fi", address=address, record=lockdown.pair_record))
            finally:
                with contextlib.suppress(Exception):
                    await lockdown.close()
    except Exception:
        pass
    return out


async def _network(timeout: float, fresh: bool) -> list[Candidate]:
    if not fresh and time.monotonic() - _browsed["at"] < BROWSE_KEEP:
        return list(_browsed["found"])
    folders: list[Path | None] = [None]
    if stored_records():
        folders.append(pairing_dir())
    found = [item for part in await asyncio.gather(*(_browse(folder, timeout) for folder in folders)) for item in part]
    _browsed["at"] = time.monotonic()
    _browsed["found"] = found
    return list(found)


async def _named(item: Candidate, spare: str) -> Candidate:
    if item.name:
        return item
    if item.id in _names:
        return _with_name(item, _names[item.id])
    name = ""
    try:
        from pymobiledevice3.lockdown import create_using_usbmux

        client = await asyncio.wait_for(
            create_using_usbmux(
                serial=item.serial,
                connection_type="USB" if item.transport == "USB" else "Network",
                autopair=False,
            ),
            4,
        )
        try:
            name = str(await client.get_value(key="DeviceName") or "")
        finally:
            with contextlib.suppress(Exception):
                await client.close()
    except Exception:
        name = ""
    if name:
        _names[item.id] = name
    return _with_name(item, name or spare or "iPhone")


def _with_name(item: Candidate, name: str) -> Candidate:
    return Candidate(item.udid, name, item.transport, item.address, item.serial, item.record)


async def discover(wifi: bool | None = None, timeout: float = BROWSE_SECONDS, fresh: bool = False) -> list[Candidate]:
    """Every device Hearth can reach. With Wi-Fi off, only the cable counts."""
    wifi = wifi_enabled() if wifi is None else wifi
    mux, network = await asyncio.gather(_usbmux(wifi), _network(timeout, fresh) if wifi else _none())
    spare = {item.id: item.name for item in network if item.name}
    rows = dedupe(mux + network)
    return list(await asyncio.gather(*(_named(item, spare.get(item.id, "")) for item in rows)))


async def _none() -> list[Candidate]:
    return []


# --- opening one --------------------------------------------------------


async def connect(item: Candidate):
    """The one way in. Over USB it pairs when it has to, and sets the phone up for Wi-Fi.
    Over Wi-Fi it never pairs."""
    from pymobiledevice3.lockdown import create_using_tcp, create_using_usbmux

    folder = pairing_dir()
    if item.transport == "USB":
        client = await create_using_usbmux(
            serial=item.serial, connection_type="USB", autopair=True, pairing_records_cache_folder=folder
        )
        await _after_cable(client)
        return client
    try:
        if item.address:
            return await create_using_tcp(
                item.address,
                identifier=item.udid,
                autopair=False,
                pair_record=item.record,
                pairing_records_cache_folder=folder,
            )
        return await create_using_usbmux(
            serial=item.serial, connection_type="Network", autopair=False, pairing_records_cache_folder=folder
        )
    except Exception as exc:
        raise CantFind() from exc


async def _after_cable(client) -> None:
    """With the cable in and Wi-Fi on: let the phone be found on the network, and keep the pairing."""
    if not wifi_enabled():
        return
    with contextlib.suppress(Exception):
        await client.set_enable_wifi_connections(True)
    with contextlib.suppress(Exception):
        keep_pair_record(client.udid, client.pair_record)


def dropped(exc: BaseException) -> bool:
    """True when a connection went away, as opposed to the phone refusing something."""
    if isinstance(exc, (OSError, TimeoutError, asyncio.TimeoutError)):
        return True
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    return "terminat" in name or "closed" in text or "broken pipe" in text or "reset" in text


class Heartbeat:
    """A phone on Wi-Fi hangs up on a connection that does not answer its pings.

    Answering costs nothing on a cable, so every connection runs it. If it cannot
    start, the work goes ahead without it.
    """

    def __init__(self, client, first_wait: float = 5.0):
        self._client = client
        self._first_wait = first_wait
        self._service = None
        self._task: asyncio.Task | None = None

    async def __aenter__(self):
        try:
            self._service = await self._client.start_lockdown_service("com.apple.mobile.heartbeat")
            await asyncio.wait_for(self._service.recv_plist(), self._first_wait)
            await self._service.send_plist({"Command": "Polo"})
        except Exception:
            await self._close()
            return self
        self._task = asyncio.create_task(self._answer())
        return self

    async def _answer(self):
        try:
            while True:
                await self._service.recv_plist()
                await self._service.send_plist({"Command": "Polo"})
        except Exception:
            pass

    async def _close(self):
        service, self._service = self._service, None
        if service is not None:
            with contextlib.suppress(Exception):
                await service.close()

    async def __aexit__(self, *exc):
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
            self._task = None
        await self._close()
