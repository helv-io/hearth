# Packaging

Push a `v*` tag, such as `v0.4.0`, to run `.github/workflows/release.yml`. The test workflow runs on every push and pull request, with no device attached.

The release workflow first creates the GitHub Release. Its notes are the matching `CHANGELOG.md` section, cut out by `scripts/release-notes.sh`. A tag whose version has no changelog section fails there, before any build starts. The build jobs then attach their files.

## Windows and macOS

`packaging/pyinstaller/hearth.spec` builds both. Windows is a one-file PyInstaller build, so the release asset is `Hearth-windows.exe` with nothing beside it. The program unpacks itself into a temporary folder on every start, which takes a few seconds, and removes the folder when it quits. macOS stays an app bundle, `Hearth.app`, zipped as `Hearth-macos.zip`, because a bundle is already one thing to the user. Neither is signed or notarized. Gatekeeper and SmartScreen will warn. Some antivirus programs distrust one-file builds, because they unpack code at run time, so a false alarm is possible until the file is signed.

The icon on Windows is `hearth/qml/hearth.ico`, set as `icon=` in the spec. The macOS bundle uses the system icon until an `.icns` is added. The window icon inside the app is `hearth/qml/hearth.png` on every platform.

### What goes in, and what stays out

The spec does not collect whole packages. PyInstaller's own hooks find what Hearth imports, and the spec then cuts what got in anyway:

- `EXCLUDED_MODULES` names Python modules that must not be bundled, such as the Qt web engine, 3D, charts, multimedia and PDF bindings.
- `DROPPED_PARTS` and `DROPPED_PLUGIN_DIRS` remove Qt libraries and plugins by name. `DROPPED_FILES` removes translations, headers, the Qt Quick Controls styles other than Basic, and the QML modules Hearth never imports.
- UPX is off. It shrinks the file further, but compressed executables are flagged by antivirus far more often.

Hearth sets the Basic style and imports only Qt Quick, Controls and Layouts. If a QML file starts importing something new, the self-test fails first, so add that module's folder to the kept set.

`qml/` is added as data. `hearth.paths.resource_dir` reads it from `sys._MEIPASS`, the folder a one-file build unpacks into. The self-test proves that on every build.

### The built-in check

`hearth --version file.txt` and `hearth --selftest file.txt` write their answer to the file, because a windowed build has no console. Without the file name they print. The self-test imports the device code, loads `Main.qml`, shows the window, grabs a picture of it and fails if the picture is blank. It reports the size of the unpacked folder too. `.github/workflows/windows.yml` and `macos.yml` build, run the check, and keep the file as an artifact. Windows runs it three times and writes the seconds to the job summary. Both also run on every push to a `cook/` branch.

## Linux Flatpak

The manifest is `packaging/flatpak/io.helv.Hearth.yml`. The runtime is `org.kde.Platform` 6.10, which supplies Qt 6. The release job uses the matching `ghcr.io/flathub-infra/flatpak-github-actions:kde-6.10` image, because that image is what actually contains `flatpak-builder`. pip installs Hearth and its dependencies into the sandbox. The finish arguments open Wayland, a fallback X11 socket, the network (icon downloads and Grok sign-in), USB, and the host usbmux socket at `/run/usbmuxd`. On Arch, `/var/run` is a symlink to `/run`, and a second permission on `/var/run/usbmuxd` makes bubblewrap refuse to start the sandbox. `--talk-name=org.freedesktop.Flatpak` lets the install button run `flatpak-spawn --host pkexec …` so usbmuxd is installed on the host. That command is chosen by Hearth. It is not a free shell. The commands live in `hearth/drivers.py`. They never appear in the sidebar until a button has failed, and then only as the folded manual steps.

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
