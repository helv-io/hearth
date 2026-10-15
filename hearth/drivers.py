"""USB service for an iPhone or iPad.

macOS already has it. Linux needs usbmuxd. Windows needs Apple Mobile
Device Support. The install commands are fixed here and are never shown
to the user. Nothing the user types is passed to a shell. Every sentence
in a Report is for people: no command names, no paths.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

SOCKETS = ("/run/usbmuxd", "/var/run/usbmuxd")
USBMUXD_FILES = ("/usr/sbin/usbmuxd", "/usr/bin/usbmuxd")
MANAGERS = ("pacman", "apt-get", "dnf", "zypper", "apk", "xbps-install")
WINGET_ID = "Apple.AppleMobileDeviceSupport"
STORE_URL = "https://apps.microsoft.com/detail/9np83lwlpz9k"
SERVICE = "Apple Mobile Device Service"
WINDOWS_EXES = (
    r"C:\Program Files\Common Files\Apple\Mobile Device Support\AppleMobileDeviceService.exe",
    r"C:\Program Files (x86)\Common Files\Apple\Mobile Device Support\AppleMobileDeviceService.exe",
)


@dataclass(frozen=True)
class Probe:
    system: str
    flatpak: bool = False
    socket_open: bool = False
    have_usbmuxd: bool = False
    have_systemctl: bool = False
    package_manager: str = ""
    windows_installed: bool = False
    windows_running: bool = False
    have_winget: bool = False


@dataclass(frozen=True)
class Report:
    """What the sidebar shows. Everything except `command` is for people.

    `command` is the fixed argv Hearth runs for the action button. It is never
    shown. `manual` is the same step as text a person can run themselves. The
    sidebar shows it only after the button has failed, folded away. `url` is a
    page to open, and `url_action` labels it as a second button when the
    command can fail.
    """

    needed: bool
    ready: bool
    kind: str
    headline: str = ""
    detail: str = ""
    action: str = ""
    manual: str = ""
    command: tuple[str, ...] = ()
    url: str = ""
    url_action: str = ""


def status(probe: Probe | None = None) -> Report:
    probe = live_probe() if probe is None else probe
    if probe.system == "Darwin":
        return _ready_mac()
    if probe.system == "Linux":
        return _linux(probe)
    if probe.system == "Windows":
        return _windows(probe)
    return Report(
        needed=True,
        ready=False,
        kind="manual",
        headline="This system is not set up",
        detail="Hearth sets up the USB service on Linux and Windows. macOS already has it.",
    )


def install() -> str:
    """Run the current plan. Returns a plain sentence for the status line."""
    report = status()
    if not report.needed or report.ready:
        return "USB support is already in place."
    if not report.command:
        return report.detail
    code, _ = _run(report.command, timeout=600)
    if report.kind in ("install", "start") and _is_windows():
        _ensure_windows_service()
    again = status()
    if again.ready or not again.needed:
        return "USB support is ready. Plug in an iPhone or iPad. Hearth reads it when it appears."
    retry = "Try again" + (", or open the Apple Devices page." if again.url_action else ".")
    if code == 126:
        return f"The password prompt was closed. {retry}"
    if code == 124:
        return f"The setup took too long. {retry}"
    if code == 127:
        return f"Hearth could not run the setup on this computer. {retry}"
    if code != 0:
        return f"The setup did not finish. {retry}"
    return f"The setup finished, but the USB service is still not running. {retry}"


def live_probe() -> Probe:
    system = _system()
    flatpak = in_flatpak()
    if system == "Linux":
        found = _linux_inventory(flatpak)
        return Probe(
            system=system,
            flatpak=flatpak,
            socket_open=found["socket"],
            have_usbmuxd=found["usbmuxd"],
            have_systemctl=found["systemctl"],
            package_manager=found["manager"],
        )
    if system == "Windows":
        installed, running = _windows_service()
        return Probe(
            system=system,
            windows_installed=installed,
            windows_running=running,
            have_winget=shutil.which("winget") is not None,
        )
    return Probe(system=system, flatpak=flatpak)


def in_flatpak() -> bool:
    return bool(os.environ.get("FLATPAK_ID")) or Path("/.flatpak-info").is_file()


def _ready_mac() -> Report:
    return Report(False, True, "ready")


def _linux(probe: Probe) -> Report:
    if probe.socket_open:
        return Report(True, True, "ready")
    if probe.have_usbmuxd:
        body = "systemctl enable --now usbmuxd" if probe.have_systemctl else "usbmuxd"
        return Report(
            True,
            False,
            "start",
            headline="The USB service is not running",
            detail="Hearth can start it for you. You may be asked for your password.",
            action="Start USB service",
            manual=_manual(body),
            command=_host(probe.flatpak, "pkexec", "sh", "-c", body),
        )
    body = _install_body(probe.package_manager, probe.have_systemctl)
    if not body:
        return Report(
            True,
            False,
            "manual",
            headline="Linux needs the USB service",
            detail="Hearth cannot set it up on this Linux by itself. Look for a package named usbmuxd in your software center, install it, then start Hearth again.",
            manual=_manual_choices(),
        )
    return Report(
        True,
        False,
        "install",
        headline="Linux needs the USB service",
        detail="The USB service lets this computer talk to an iPhone or iPad over a cable. Hearth installs it for you. You may be asked for your password.",
        action="Install USB service",
        manual=_manual(body),
        command=_host(probe.flatpak, "pkexec", "sh", "-c", body),
    )


def _windows(probe: Probe) -> Report:
    if probe.windows_running:
        return Report(True, True, "ready")
    if probe.windows_installed:
        return Report(
            True,
            False,
            "start",
            headline="Apple's USB driver is not running",
            detail="It is installed. Hearth can start it for you. You may be asked to approve it.",
            action="Start USB driver",
            manual=f'net start "{SERVICE}"',
            command=("net", "start", SERVICE),
        )
    if probe.have_winget:
        return Report(
            True,
            False,
            "install",
            headline="Windows needs Apple's USB driver",
            detail="The driver lets this PC talk to an iPhone or iPad over a cable. Hearth installs it for you. You may be asked to approve it.",
            action="Install USB driver",
            manual=f"winget install -e --id {WINGET_ID}",
            command=(
                "winget",
                "install",
                "-e",
                "--id",
                WINGET_ID,
                "--accept-package-agreements",
                "--accept-source-agreements",
                "--disable-interactivity",
            ),
            url=STORE_URL,
            url_action="Open Apple Devices page",
        )
    return Report(
        True,
        False,
        "browse",
        headline="Windows needs Apple's USB driver",
        detail="Hearth cannot install it by itself on this PC. Open the Apple Devices page, install it from the Microsoft Store, then come back. iTunes from Apple also works.",
        action="Open Apple Devices page",
        url=STORE_URL,
    )


def _install_body(manager: str, have_systemctl: bool) -> str:
    start = " && systemctl enable --now usbmuxd" if have_systemctl else " && usbmuxd"
    if manager == "pacman":
        return f"pacman -S --needed --noconfirm usbmuxd{start}"
    if manager == "apt-get":
        return f"export DEBIAN_FRONTEND=noninteractive; apt-get update && apt-get install -y usbmuxd{start}"
    if manager == "dnf":
        return f"dnf install -y usbmuxd{start}"
    if manager == "zypper":
        return f"zypper --non-interactive install usbmuxd{start}"
    if manager == "apk":
        return "apk add --no-cache usbmuxd && (rc-service usbmuxd start || usbmuxd)"
    if manager == "xbps-install":
        return f"xbps-install -y usbmuxd{start}"
    return ""


def _manual(body: str) -> str:
    return f"pkexec sh -c {shlex.quote(body)}"


def _manual_choices() -> str:
    return "\n".join((
        "Arch: sudo pacman -S usbmuxd && sudo systemctl enable --now usbmuxd",
        "Debian: sudo apt install usbmuxd",
        "Fedora: sudo dnf install usbmuxd && sudo systemctl enable --now usbmuxd",
    ))


def _host(flatpak: bool, *args: str) -> tuple[str, ...]:
    if flatpak:
        return ("flatpak-spawn", "--host", *args)
    return args


def _linux_inventory(flatpak: bool) -> dict[str, object]:
    if not flatpak:
        manager = next((name for name in MANAGERS if shutil.which(name)), "")
        usbmuxd = shutil.which("usbmuxd") is not None or any(Path(path).is_file() for path in USBMUXD_FILES)
        return {
            "socket": any(Path(path).exists() for path in SOCKETS),
            "usbmuxd": usbmuxd,
            "systemctl": shutil.which("systemctl") is not None,
            "manager": manager,
        }
    script = """
socket=0
if [ -S /run/usbmuxd ] || [ -S /var/run/usbmuxd ]; then socket=1; fi
printf 'SOCKET=%s\\n' "$socket"
if command -v usbmuxd >/dev/null || [ -x /usr/sbin/usbmuxd ] || [ -x /usr/bin/usbmuxd ]; then
  echo USBMUXD=1
else
  echo USBMUXD=0
fi
if command -v systemctl >/dev/null; then echo SYSTEMCTL=1; else echo SYSTEMCTL=0; fi
for c in pacman apt-get dnf zypper apk xbps-install; do
  if command -v "$c" >/dev/null; then echo "MANAGER=$c"; break; fi
done
"""
    code, text = _run(("flatpak-spawn", "--host", "sh", "-c", script), timeout=8)
    found: dict[str, object] = {"socket": False, "usbmuxd": False, "systemctl": False, "manager": ""}
    if code != 0:
        return found
    for line in text.splitlines():
        if line == "SOCKET=1":
            found["socket"] = True
        elif line == "USBMUXD=1":
            found["usbmuxd"] = True
        elif line == "SYSTEMCTL=1":
            found["systemctl"] = True
        elif line.startswith("MANAGER="):
            found["manager"] = line.split("=", 1)[1].strip()
    return found


def _windows_service() -> tuple[bool, bool]:
    exe = any(Path(path).is_file() for path in WINDOWS_EXES)
    try:
        completed = subprocess.run(
            ["sc", "query", SERVICE],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
            **_quiet(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return exe, False
    text = f"{completed.stdout}\n{completed.stderr}"
    installed = exe or completed.returncode == 0 or "SERVICE_NAME" in text
    return installed, "RUNNING" in text


def _ensure_windows_service() -> None:
    if not _is_windows():
        return
    _run(("net", "start", SERVICE), timeout=30)
    _, running = _windows_service()
    if running:
        return
    _run((
        "powershell",
        "-NoProfile",
        "-Command",
        "Start-Process -WindowStyle Hidden -FilePath net -ArgumentList 'start \"Apple Mobile Device Service\"' -Verb RunAs -Wait",
    ), timeout=180)


def _system() -> str:
    import platform
    return platform.system()


def _is_windows() -> bool:
    return _system() == "Windows"


def _quiet() -> dict[str, object]:
    """Keep a helper command from reading input or opening a console window.

    Hearth on Windows has no console of its own, so each helper would flash one.
    """
    kwargs: dict[str, object] = {"stdin": subprocess.DEVNULL}
    if _is_windows():
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


def _run(argv: tuple[str, ...] | list[str], timeout: int) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            **_quiet(),
        )
    except subprocess.TimeoutExpired:
        return 124, "Timed out."
    except OSError as exc:
        return 127, str(exc)
    text = (completed.stderr or completed.stdout or "").strip()
    if len(text) > 280:
        text = text[-280:]
    return completed.returncode, " ".join(text.split())
