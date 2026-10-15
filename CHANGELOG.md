# Changelog

## Unreleased

- Hearth checks the OS at startup. macOS needs nothing. Linux offers to install and start `usbmuxd`. Windows offers Apple Mobile Device Support through winget, or opens Apple Devices when winget is missing.
- A plugged-in device is noticed on its own. Refresh checks again without replacing the canvas. The buttons are Read from Device and Send to Device.
- Messages and docs use Read from Device and Send to Device. Nothing says pull or push any more. Two devices at once now say to unplug one, and the readme explains why.
- The readme names the Windows program `hearth.exe`, which is what the build makes.

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
