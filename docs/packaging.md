# Packaging

Push a `v*` tag, such as `v0.2.1`, to run `.github/workflows/release.yml`. The test workflow runs on every push and pull request, with no device attached.

## Windows and macOS

PyInstaller builds an onedir app from `packaging/pyinstaller/hearth.spec`. The Windows zip contains `hearth.exe`. The macOS zip contains `Hearth.app`. Neither is signed or notarized. Gatekeeper and SmartScreen will warn. The icon on Windows is `hearth/qml/hearth.ico`. The macOS bundle uses the system icon until an `.icns` is added. The window icon inside the app is `hearth/qml/hearth.png` on every platform.

The spec collects PySide6 and pymobiledevice3. QML is unpacked beside the frozen program as `qml/`, which is where `hearth.paths.resource_dir` looks.

## Linux Flatpak

The manifest is `packaging/flatpak/io.helv.Hearth.yml`. The runtime is `org.kde.Platform` 6.10, which supplies Qt 6. The release job uses the matching `ghcr.io/flathub-infra/flatpak-github-actions:kde-6.10` image, because that image is what actually contains `flatpak-builder`. pip installs Hearth and its dependencies into the sandbox. The finish arguments open Wayland, a fallback X11 socket, the network (icon downloads and Grok sign-in), USB, and the host usbmux sockets at `/run/usbmuxd` and `/var/run/usbmuxd`.

Install a bundle with:

```bash
flatpak install --user hearth.flatpak
flatpak run io.helv.Hearth
```

The host still needs `usbmuxd`. The sandbox does not run its own copy.

If Flathub retires the 6.10 runtime, bump `runtime-version`, the container image tag, and the cache key together.

## Local check

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
make test
```

A full Flatpak build needs `flatpak-builder` and the KDE SDK. It is large. CI is the place that produces the bundle.
