# Packaging

Push a `v*` tag, such as `v0.4.0`, to run `.github/workflows/release.yml`. The test workflow runs on every push and pull request, with no device attached.

The release workflow first creates the GitHub Release. Its notes are the matching `CHANGELOG.md` section, cut out by `scripts/release-notes.sh`. A tag whose version has no changelog section fails there, before any build starts. The build jobs then attach their files.

## Windows and macOS

`packaging/pyinstaller/hearth.spec` builds both. Windows is a one-file PyInstaller build, so the release asset is `Hearth-windows.exe` with nothing beside it. The program unpacks itself into a temporary folder on every start, which takes a few seconds, and removes the folder when it quits. macOS stays an app bundle, `Hearth.app`, and is released inside a disk image. There are two, one per kind of Mac: `Hearth-macos.dmg` for Apple silicon (M1 and newer) and `Hearth-macos-intel.dmg` for Intel. The bundle is already one thing to the user, and the image gives the familiar drag-to-Applications window. Neither is signed or notarized. Gatekeeper and SmartScreen will warn. Some antivirus programs distrust one-file builds, because they unpack code at run time, so a false alarm is possible until the file is signed.

### Two Mac builds

`macos.yml` is a two-row matrix. Each row builds on a runner of its own kind, so the app and the self-test run natively, with no Rosetta:

| File | Runner | Architecture |
| --- | --- | --- |
| `Hearth-macos.dmg` | `macos-latest` | arm64 |
| `Hearth-macos-intel.dmg` | `macos-15-intel` | x86_64 |

They are two plain builds, not one universal2 app. A universal app would have to merge Qt and PySide6 libraries and would be about twice the size for everyone. The Apple silicon file keeps the plain name. Only the Intel file carries a tag.

Each row checks, before and after the disk image: that the runner is the expected kind and not translated, that the app's main program and every program and library inside carry that architecture, that the self-test reports the same machine, and that the bundle version matches the package. The job summary lists the oldest macOS the build asks for and which parts set it.

**Intel runners end in August 2027.** GitHub's last Intel Mac image is macOS 15, label `macos-15-intel`. `macos-13` was retired in December 2025. Check the label against the [runner images list](https://github.com/actions/runner-images#available-images) before each release. When GitHub drops Intel, the Intel row has to move to something else, such as a self-hosted Intel Mac, or stop, and the README and release notes must say so.

**Dependencies are installed as wheels only.** `cryptography` 50 has no Intel Mac wheel. Without the wheels-only rule, pip compiled it on the Intel runner, which took minutes, and it linked the runner's older OpenSSL. The app then failed to start with a missing `SSL_get0_group_name` symbol. With wheels only, pip picks `cryptography` 48 on Intel, which has a universal2 wheel with OpenSSL built in. The step fails with the package name if some dependency ever has no wheel for a platform.

**Oldest macOS.** Qt 6.12 documents macOS 14.4 as its minimum, and the README says so. The PySide6 6.12 binding libraries are marked as built for macOS 26 in their headers, although the wheel tag says 14. This has not been tried on a real Mac older than 26.

### The macOS disk image

`packaging/macos/dmg-settings.py` describes the image for [dmgbuild](https://dmgbuild.readthedocs.io), a pure Python tool that needs only the `hdiutil` that ships with macOS. Hearth.app sits on the left, a shortcut to Applications on the right, with dmgbuild's built-in arrow between them, and the volume is named Hearth. dmgbuild writes the window layout itself instead of scripting Finder, which is why it works on a CI runner with no desktop session. Each row of `macos.yml` builds the app, runs the built-in check on it, makes the image, mounts it, compares the bundle version with the package version, and runs the check again on the app inside the mounted image. The app version comes from the package, through the spec. The image is plain HFS+ with compression, which every Mac that can run Hearth reads.

The app is unsigned and not notarized, so the first open is blocked by Gatekeeper. Since macOS 15 the old right-click and Open shortcut no longer works. The person has to try once, then use Open Anyway in System Settings under Privacy & Security. The README says so in plain words. If the project ever gets an Apple developer account, sign and notarize the app before `dmgbuild`, then sign and notarize the image, and drop that README section.

The icon on Windows is `hearth/qml/hearth.ico`, set as `icon=` in the spec. The macOS app icon is `Hearth.icns`, built in CI by `packaging/macos/make-icns.sh` (sips and iconutil: 16 to 512 px, each with an @2x twin) from the master `packaging/macos/icon-1024.png`. The spec passes it as the BUNDLE `icon=` and names it in `CFBundleIconFile`, and fails the build if the file is missing. dmgbuild gets the same file as the disk's icon (`-D icon=`). Before 0.5.4 the bundle had none, and Finder and the Dock showed the generic script icon.

The master comes from `scripts/make-mac-icon.py`, run by hand when the artwork changes. `hearth.png` is a tile on a dark square. The script cuts the tile out, rounds it, adds a soft shadow and puts it on a transparent canvas with the clear space Apple's icon grid asks for. The same picture at 512 px is `hearth/qml/hearth-macos.png`, which the app sets as its window and Dock icon on macOS, so the running app matches the file. Other platforms use `hearth/qml/hearth.png`. The art is a 256 px source, so the biggest sizes are enlarged and a little soft. A larger source would sharpen them.

`macos.yml` checks the built app for both Macs: `Info.plist` is valid and names an icon, the file is in `Contents/Resources`, is identical to the one made, and unpacks to every size. The mounted image must hold the app's icon and `.VolumeIcon.icns`. The icon is also drawn to a picture and uploaded as the `icon-check-arm64` and `icon-check-x86_64` artifacts, so the real icon can be looked at.

### What goes in, and what stays out

The spec does not collect whole packages. PyInstaller's own hooks find what Hearth imports, and the spec then cuts what got in anyway:

- `EXCLUDED_MODULES` names Python modules that must not be bundled, such as the Qt web engine, 3D, charts, multimedia and PDF bindings.
- `DROPPED_PARTS` and `DROPPED_PLUGIN_DIRS` remove Qt libraries and plugins by name. `DROPPED_FILES` removes translations, headers, the Qt Quick Controls styles other than Basic, and the QML modules Hearth never imports.
- UPX is off. It shrinks the file further, but compressed executables are flagged by antivirus far more often.

Hearth sets the Basic style and imports only Qt Quick, Controls and Layouts. If a QML file starts importing something new, the self-test fails first, so add that module's folder to the kept set.

`qml/` is added as data. `hearth.paths.resource_dir` reads it from `sys._MEIPASS`, the folder a one-file build unpacks into. The self-test proves that on every build.

### The built-in check

`hearth --version file.txt` and `hearth --selftest file.txt` write their answer to the file, because a windowed build has no console. Without the file name they print. The self-test reports which machine it ran on, checks that the bundled certificate list is there, imports the device code, loads `Main.qml`, shows the window, grabs a picture of it and fails if the picture is blank. It reports the size of the unpacked folder too. `.github/workflows/windows.yml` and `macos.yml` build, run the check, and keep the file as an artifact. Windows runs it three times and writes the seconds to the job summary. Both also run on every push to a `cook/` branch.

## Linux Flatpak

The manifest is `packaging/flatpak/io.helv.Hearth.yml`. The runtime is `org.kde.Platform` 6.10, which supplies Qt 6. PySide6 comes from the Flathub base app `io.qt.PySide.BaseApp` 6.10, built against that runtime. Do not install PySide6 from PyPI here: its wheel carries a second copy of Qt that needs `libgssapi_krb5`, which the runtime lacks, and 0.6.1 shipped a Flatpak that could not start because of it. The manifest installs `pymobiledevice3` on its own and Hearth with `--no-deps`; a test keeps that line in step with `pyproject.toml`. The release job uses the matching `ghcr.io/flathub-infra/flatpak-github-actions:kde-6.10` image, because that image is what actually contains `flatpak-builder`. pip installs the other dependencies and Hearth into the sandbox. The finish arguments open Wayland, a fallback X11 socket, the network (icon downloads and Grok sign-in), USB, and the host usbmux socket at `/run/usbmuxd`. On Arch, `/var/run` is a symlink to `/run`, and a second permission on `/var/run/usbmuxd` makes bubblewrap refuse to start the sandbox. `--talk-name=org.freedesktop.Flatpak` lets the install button run `flatpak-spawn --host pkexec …` so usbmuxd is installed on the host. That command is chosen by Hearth. It is not a free shell. The commands live in `hearth/drivers.py`. They never appear in the sidebar until a button has failed, and then only as the folded manual steps.

Install a bundle with:

```bash
flatpak install --user hearth.flatpak
flatpak run io.helv.Hearth
```

The host still needs `usbmuxd`. The sandbox does not run its own copy. The in-app button installs it on the host when it is missing.

If Flathub retires the 6.10 runtime, bump `runtime-version`, the container image tag, and the cache key together.

## Update check

`hearth/updates.py` is the whole feature. `REPO` is the one place that names the project, and the tag list URL and the download page are built from it. A test checks it against the Homepage in `pyproject.toml`.

At startup `Controller.startUpdateCheck` runs `updates.offer` on a background thread. `offer` reads `updates.json` in the config directory. That file holds `enabled`, `latest` and `skipped`. It is separate from `settings.json` on purpose, because saving the model settings rewrites that file. Every start makes one unauthenticated request to `https://api.github.com/repos/helv-io/hearth/tags?per_page=100` with a 5 second timeout. The newest `vX.Y.Z` tag that is not a pre-release wins, compared by number, not by text, so `v0.10.0` beats `v0.9.0`. Other tags are ignored.

There is no daily limit. A failure of any kind, a rate limit, no connection or an odd answer, shows nothing at start, and the saved `latest` from the last good answer is used, so a person who pressed Not now still sees the card. The next start asks again.

The Settings button calls `Controller.checkForUpdatesNow`, which runs `updates.check_now` on its own thread. It ignores the startup toggle and `skipped`, because the person asked, and it reports `newer`, `current` or `failed`. Newer sets the same card as at start. Current and failed show "You're up to date." and "Couldn't check right now. Try again." under the button. Only the button shows busy ("Checking…"); `busy` is not touched, so nothing else locks. The card sits above the Settings overlay (z 22), so the answer is never hidden behind it. An answer with no usable release tag counts as failed, not as up to date. A build with no readable version, `0.0.0`, or a `dev` marker never asks. `--version` and `--selftest` never ask, and a test proves the self-test makes no network call.

GitHub does not list tags in version order, and returns 100 at most. That is plenty while tags follow `vX.Y.Z`. If the project ever has more than 100 tags, read `releases/latest` instead.

## Local check

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
make test
```

`.github/workflows/flatpak.yml` builds the bundle, installs it with `flatpak install --bundle`, and starts it with no screen (`import hearth.__main__`, then `hearth --selftest`, which must print `ok`). The release workflow calls it and attaches the file only after it passed. It also runs on pull requests that touch the manifest and on `cook/**` branches.

A full Flatpak build needs `flatpak-builder` and the KDE SDK. It is large. CI is the place that produces the bundle.
