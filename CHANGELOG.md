# Changelog

## 0.3.0 — 2026-10-15

Hearth notices a device, sets up the USB service for you, and shows folder pages.

- A plugged-in device is noticed on its own, and the layout is read when the canvas has no unsaved edits. Refresh checks again without replacing the canvas.
- Hearth checks the OS at startup. macOS needs nothing. Linux offers to install and start `usbmuxd`. Windows offers Apple Mobile Device Support through winget, or opens Apple Devices when winget is missing. The Linux Flatpak runs the same command on the host.
- A folder with two or more pages shows that count in a red badge. Holding an icon at the edge of a page strip scrolls it, on the home screen and in the folder drawer. Pulling the folder handle down closes the drawer.
- The buttons are Read from Device and Send to Device. Messages and docs no longer say pull or push.
- Two devices at once say to unplug one, and the readme explains why.
- Plainer wording for the USB service, the install buttons, the Flatpak, and the note on supervised devices. The sidebar tells you to copy the command and run it yourself if the button fails.
- The readme names the Windows program `hearth.exe`, which is what the build makes.
- On Windows, the driver install and the service checks no longer flash console windows.
- The GitHub Release notes come from this changelog.
- Tests and builds: CI runs on every push to master. The macOS app takes its version from the package. The version test checks the package, `pyproject.toml`, the Linux metainfo, and this changelog.

## 0.2.1 — 2026-10-15

The Flatpak release job runs inside the KDE 6.10 builder image, which is the runtime image published for that action. The 0.2.0 job failed immediately because the plain Ubuntu runner has no `flatpak-builder`.

## 0.2.0 — 2026-10-15

First published release. The program is named Hearth.

- An iPhone uses a 4×6 grid and a dock of 4. An iPad uses the 6×5 grid and a dock of up to 15, folders included. A model older than the current OS still opens, with a warning. An unknown newer model opens on its family grid.
- Connecting accepts the Trust prompt. Two devices at once ask you to unplug one.
- Saved versions remember the screen. Versions written before that open as an iPhone. An existing `iphone-layout` data directory is left in place.
- Windows, macOS, and Linux Flatpak release builds run from a version tag.
- The command is `hearth`. `iphone-layout` still starts it.

## 0.1.0

Local editor only. It was not published. Pages can keep empty cells, folders stay packed, and a push strips those editor coordinates.
