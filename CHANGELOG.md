# Changelog

## Unreleased

The Linux Flatpak is rebuilt to the rules Flathub asks for.

- The Flatpak no longer asks to run commands on the computer, so the install button is gone from it. If the USB service is not visible, Hearth says so in plain words and folds away the steps to run yourself. Other builds keep the button.
- The Flatpak builds with no network, from pinned sources, on the KDE 6.11 runtime, with PySide6 from the Flathub base app.
- The Linux metainfo has screenshots, a developer, links and release pages. The desktop file has keywords.
- Docs: `docs/flathub.md` says what Flathub needs and what is still open.

## 0.5.0 — 2026-10-15

Hearth tells you when a newer version is out, and the Mac download is a disk image.

- macOS is a disk image, `Hearth-macos.dmg`, instead of a zip. Open it and drag Hearth onto the Applications shortcut in the window. It is still unsigned, so the first open needs extra clicks, and the readme now lists them for newer and older versions of macOS. Right-click and Open, which used to be enough, no longer works on macOS 15 and newer.
- The macOS build is for Macs with Apple silicon, M1 and newer. The readme says so.
- Every macOS build opens its own disk image and starts the app from inside it before anything is published.
- Hearth checks at startup whether a newer version exists. A small card says "Hearth X.Y.Z is available" with Open download page, Not now and Skip this version. It asks GitHub at most once a day and stays quiet when you are offline. Settings has a Check for updates on startup box, on by default. That request is the only thing Hearth sends on its own, and it carries nothing about you or your device.

## 0.4.0 — 2026-10-15

Windows is one small file, and the downloads are about a fifth of their old size.

- Windows is a single `Hearth-windows.exe`. Download it and double-click. There is no zip and no folder beside it. It unpacks itself for a few seconds on each start.
- The Windows file is about 60 MB, down from a 340 MB zip that held an 850 MB folder. The macOS download is about 60 MB, down from 270 MB. Hearth only carries the parts of Qt it uses. The web browser engine, 3D, charts, audio and video, the other window styles and the translations are gone.
- Every Windows and macOS build now starts itself once, with no device attached, and checks that the window draws before anything is published.
- The saved versions list says Read from Device, Sent to Device and Before send, the same words as the buttons. It used to say pull, pushed and before push. Versions you saved earlier keep working and show the new words.
- A saved version opened after Hearth restarts shows its real icons. They used to appear only after a read from the device, so an older version could come up as letter tiles.
- Docs: the README has screenshots of a sample home screen.
- Tests and builds: the Windows and macOS builds are their own workflows, which the release calls, and which also run on `cook/` branches. The Windows build fails if the file grows past a size limit. Details are in `docs/packaging.md`.

## 0.3.0 — 2026-10-15

Hearth notices a device, sets up the USB service for you, and shows folder pages.

- A plugged-in device is noticed on its own, and the layout is read when the canvas has no unsaved edits. Refresh checks again without replacing the canvas.
- Hearth checks at startup that the USB service for iPhones and iPads is there. macOS needs nothing. On Linux and Windows one button installs and starts it for you, and on Windows it can open the Apple Devices page instead.
- A folder with two or more pages shows that count in a red badge. Holding an icon at the edge of a page strip scrolls it, on the home screen and in the folder drawer. Pulling the folder handle down closes the drawer.
- The buttons are Read from Device and Send to Device. Messages and docs no longer say pull or push.
- Two devices at once say to unplug one, and the readme explains why.
- The USB setup speaks plainly. The sidebar and the buttons name no commands: Install USB service, Start USB service, Install USB driver, Start USB driver. A failed setup says what went wrong and offers a retry, and on Windows the Apple Devices page. Only after a failure does a folded Show manual steps appear, with the exact step and a Copy button.
- The note on supervised devices in the readme is in everyday words.
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
