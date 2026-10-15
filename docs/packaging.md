# Packaging

Push a `v*` tag, such as `v0.3.0`, to run `.github/workflows/release.yml`. The test workflow runs on every push and pull request, with no device attached.

The release workflow first creates the GitHub Release. Its notes are the matching `CHANGELOG.md` section, cut out by `scripts/release-notes.sh`. A tag whose version has no changelog section fails there, before any build starts. The build jobs then attach their files.

## Windows and macOS

PyInstaller builds an onedir app from `packaging/pyinstaller/hearth.spec`. The Windows zip contains `hearth.exe`. The macOS zip contains `Hearth.app`. Neither is signed or notarized. Gatekeeper and SmartScreen will warn. The icon on Windows is `hearth/qml/hearth.ico`. The macOS bundle uses the system icon until an `.icns` is added. The window icon inside the app is `hearth/qml/hearth.png` on every platform.

The spec collects PySide6 and pymobiledevice3. QML is unpacked beside the frozen program as `qml/`, which is where `hearth.paths.resource_dir` looks.

## Linux Flatpak

The manifest is `packaging/flatpak/io.helv.Hearth.yml`. The runtime is `org.kde.Platform` 6.10, which supplies Qt 6. The release job uses the matching `ghcr.io/flathub-infra/flatpak-github-actions:kde-6.10` image, because that image is what actually contains `flatpak-builder`. pip installs Hearth and its dependencies into the sandbox. The finish arguments open Wayland, a fallback X11 socket, the network (icon downloads and Grok sign-in), USB, and the host usbmux socket at `/run/usbmuxd`. On Arch, `/var/run` is a symlink to `/run`, and a second permission on `/var/run/usbmuxd` makes bubblewrap refuse to start the sandbox. `--talk-name=org.freedesktop.Flatpak` lets the install button run `flatpak-spawn --host pkexec …` so usbmuxd is installed on the host. That command is chosen by Hearth. It is not a free shell.

Install a bundle with:

```bash
flatpak install --user hearth.flatpak
flatpak run io.helv.Hearth
```

The host still needs `usbmuxd`. The sandbox does not run its own copy. The in-app button installs it on the host when it is missing.

If Flathub retires the 6.10 runtime, bump `runtime-version`, the container image tag, and the cache key together.

## Local check

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
make test
```

A full Flatpak build needs `flatpak-builder` and the KDE SDK. It is large. CI is the place that produces the bundle.
