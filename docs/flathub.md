# Publishing Hearth on Flathub

Status: prepared, not submitted. Nothing here has been sent to Flathub. This page is the working notes for whoever submits it, and it says what is done, what is risky, and what only the maintainer can do.

## Read this first

Three Flathub rules decide whether Hearth gets in. Check them again before submitting, because the policies change. They are on https://docs.flathub.org/docs/for-app-authors/requirements.

1. **Generative AI policy.** Flathub manifests must not contain AI-generated or AI-assisted content, and a disclosure does not excuse that. Any AI-generated code, docs or packaging in the app must be disclosed, with the affected parts and the rough extent. AI tools must not open the submission pull request, write its commit messages or description, or answer reviewers. Hearth was written with an AI assistant, and so was everything in `packaging/flatpak`, `packaging/linux`, `scripts/flathub-manifest.sh` and this page. So the person who submits has to write the submission manifest by hand, can use the files here as a reference only, must disclose the AI use in their own words, and has to open and handle the pull request without an assistant. Regenerating the source lists with the standard tools (below) is the safest way to get files that are plainly tool output.
2. **Host-dependent applications.** Flathub does not accept apps that rely on host components for core functionality, except case by case. Hearth cannot talk to a phone without `usbmuxd` running on the computer. That is the weakest point of the submission. Ask the reviewers early, in an issue or on the Flathub Matrix room, before spending more time. See "The USB service" below.
3. **Insufficient development history.** Flathub wants a meaningful history, real use and tagged releases. The repository is new. Wait for some weeks of releases, stars and issues. The README plan already says early to mid November at the soonest.

Smaller things that can still stop it:

- The runtime must be the latest one on Flathub on the day of submission. Today that is KDE 6.11. Bump `runtime-version`, `base-version`, the `rust-stable` extension branch if the freedesktop base moves, the CI image tag, and rerun `update-sources.py`.
- The screenshots show real App Store icons. Flathub's trademark rule says nothing in the app's presentation may infringe trademarks. Reviewers may object. Consider retaking the Flathub screenshots with made-up icons.
- Helvio's GitHub account needs two-factor authentication before the invitation to the new Flathub repository, and it must be accepted within a week.

## What is in the repository

| File | What it is |
| --- | --- |
| `packaging/flatpak/io.helv.Hearth.yml` | The manifest. Its hearth source is the working tree, so CI and the release job build the current checkout. |
| `packaging/flatpak/python3-*.yaml`, `cargo-sources-*.json` | The pinned, offline sources, made by `update-sources.py`. Do not edit by hand. |
| `packaging/flatpak/requirements.txt`, `requirements-build.txt` | The only inputs to the generator. Exact pins. |
| `packaging/flatpak/update-sources.py` | Regenerates the files above. |
| `scripts/flathub-manifest.sh` | Makes the folder for the Flathub repository: the same manifest with the hearth source set to a release tag and its commit. |
| `packaging/linux/io.helv.Hearth.metainfo.xml`, `.desktop` | AppStream and desktop file. |
| `.github/workflows/flathub.yml` | Builds the manifest offline, lints it, and starts the app. Runs on `cook/` branches and by hand. |
| `tests/test_flatpak.py` | Offline unit checks of the manifest and metainfo. They run in normal CI. |

## How the build works

The build runs with no network, as Flathub's does. `flatpak-builder` downloads every source first, and each is pinned by checksum or commit. Nothing in the manifest asks for network access while building, and `tests/test_flatpak.py` fails if that changes.

**PySide6 comes from `io.qt.PySide.BaseApp` (6.11).** That is what Flathub prefers. The base app builds PySide6 against the KDE runtime, so Qt is not bundled twice, and no pre-built PySide6 wheel (hundreds of megabytes of Qt) is downloaded. The pip route was the alternative. It works but ships its own Qt, is far larger, and installs pre-built binaries, which Flathub discourages. The base app also carries web engine parts, numpy and build tools that Hearth never uses, so the manifest turns on the base app's own switches (`BASEAPP_REMOVE_WEBENGINE`, `BASEAPP_DISABLE_NUMPY`) and removes the build-only leftovers. The installed app is about 150 MB and the bundle about 27 MB.

**Python dependencies are a short, exact list.** `pymobiledevice3` declares about 100 dependencies for its whole command line tool, including `av`, `pillow`, `pydantic`, `fastapi` and `ipython`. Hearth only imports `pymobiledevice3.lockdown`, `.usbmux` and `.services.springboard`. Those need `construct`, `cryptography`, `ifaddr`, `psutil`, `pygments`, `questionary`, `requests`, `tqdm` and `typing_extensions`, plus what those need. `requirements.txt` holds exactly that, and `pymobiledevice3` is installed with `--no-deps`. Building the full list offline would mean `av` with ffmpeg and several more Rust packages. The built app's `--selftest` proves the imports work. If Hearth starts importing another part of `pymobiledevice3`, add what it needs to `requirements.txt` and regenerate.

**`cryptography` is built from source.** It is a Rust package and Flathub wants it built from source. The manifest uses the `rust-stable` SDK extension, vendors the crates from the sdist's `Cargo.lock` with `flatpak-cargo-generator`, and builds `maturin` first, also from source, to drive it. Those build tools are removed again at the end. It adds about five minutes to a clean build. The simpler fallback is to take the pre-built `cryptography` wheel and drop `python3-maturin.yaml` and the cargo files. It is faster but ships a binary, so reviewers may refuse it.

**Pure Python packages use their wheels.** They are plain files with no compiled code, and checksums pin them.

## Permissions, and why

| Permission | Why |
| --- | --- |
| `--share=ipc`, `--socket=wayland`, `--socket=fallback-x11`, `--device=dri` | A Qt Quick window with GPU drawing. |
| `--share=network` | Downloading app icons, the model provider the person chooses for Organize, Sign in with Grok, and the once-a-day update check. |
| `--filesystem=/run/usbmuxd` | The socket of the host's USB service. It is how Hearth reaches the phone. |

There is no `--device=all`. The sandbox never touches USB itself. There is no home or host file access, because layouts and settings live in the app's own data directory.

### The USB service

The old manifest had `--talk-name=org.freedesktop.Flatpak`, which let the install button run `flatpak-spawn --host pkexec ...` on the computer. **It is removed.** Flathub's linter rejects it (`finish-args-flatpak-spawn-access`), and a sandboxed app that can run commands outside the sandbox defeats the point of the sandbox. A reviewer would not accept it. The replacement:

- In Flatpak, `hearth/drivers.py` runs nothing on the computer. If the socket is missing it shows the plain message "Hearth cannot see the USB service", with a folded manual-steps section for Arch, Debian and Fedora, which the existing card already supports.
- The metainfo description says that `usbmuxd` has to be present, as the Flathub rules ask for post-install steps to be mentioned.
- The `.flatpak` bundle from the release page behaves the same. The one-click install button remains for the other builds, and is gone from the Flatpak by design.

Known limit: `/run/usbmuxd` exists only while `usbmuxd` runs. On many systems a udev rule starts it when the phone is plugged in and stops it when the last phone is removed. Flatpak only mounts the socket if it exists when the app starts, so Hearth must be started with the phone already plugged in, and a phone plugged in later is not noticed. Other apps hit the same wall (iDescriptor on Flathub, OBS plugins). The fixes all change the host: a systemd socket unit that keeps `/run/usbmuxd`, or removing the udev rule that stops the daemon. If Hearth ever documents one of those, say so in the metainfo and README. This limit should be tested on a real Linux machine with a real phone before submitting. It has not been.

## Checks that were run

On a Debian 13 box with Flatpak 1.16, `flatpak-builder` 1.4.4 and the Flathub `org.flatpak.Builder`:

- `appstreamcli validate --pedantic` on the metainfo: passes. The only note is the capital letters in the ID, which Flathub requires to match.
- `desktop-file-validate`: passes.
- `flatpak-builder-lint manifest`: no errors.
- `flatpak-builder-lint appstream` on the metainfo: passes.
- An offline `flatpak-builder` build of the manifest: works, including `cryptography` and `maturin` from source. The built app starts and `hearth --selftest` loads the window and the device code inside the sandbox.
- `flatpak-builder-lint builddir` and `repo` on a local build: the only errors are `appstream-external-screenshot-url` and `appstream-screenshots-not-mirrored-in-ostree`. Both are expected on any local build. Flathub's builders mirror the screenshots to its own server, and the screenshot URLs only work once the tag exists. Everything else is clean.
- Not tested: a real phone, a Wayland session, `aarch64`.

The same checks run in `.github/workflows/flathub.yml`.

## Before each release

1. Bump the version everywhere (`hearth/__init__.py`, `pyproject.toml`, the changelog, the first `<release>` in the metainfo) and the version in the four screenshot URLs. `tests/test_flatpak.py` checks they agree.
2. Tag and release as usual.
3. If dependencies changed: `python3 packaging/flatpak/update-sources.py` (see its docstring for what to install), then commit the result.
4. After submission, an update to Flathub is a pull request to `flathub/io.helv.Hearth` that changes the `tag` and `commit` of the hearth source and anything the generator changed. It does not go through the new-app process.

## Local build and lint

```bash
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub org.flatpak.Builder org.kde.Platform//6.11 org.kde.Sdk//6.11 \
  io.qt.PySide.BaseApp//6.11 org.freedesktop.Sdk.Extension.rust-stable//26.08

# Build the working tree (use the Flathub variant, below, for a release).
flatpak-builder --user --force-clean --repo=repo build packaging/flatpak/io.helv.Hearth.yml
flatpak build-bundle repo hearth.flatpak io.helv.Hearth
flatpak install --user hearth.flatpak
flatpak run io.helv.Hearth

lint() { flatpak run --filesystem="$PWD" --command=flatpak-builder-lint org.flatpak.Builder "$@"; }
lint manifest packaging/flatpak/io.helv.Hearth.yml
lint appstream packaging/linux/io.helv.Hearth.metainfo.xml
lint repo repo
```

If `flatpak install` fails with "Could not connect: No such file or directory" on a machine with no system bus, start one (`sudo dbus-daemon --system --fork`) or run it from a normal desktop session.

## Submission steps (to do by hand, later)

Only after the items above are settled, and with no AI tool involved in writing or opening the pull request.

1. Tag a release, for example `v0.6.0`, and make sure the four screenshot URLs in the metainfo load.
2. Make the Flathub folder from the tag:
   ```bash
   scripts/flathub-manifest.sh v0.6.0 /tmp/io.helv.Hearth
   ```
   Then read the manifest yourself, edit it into your own words and style, and check the key order against the Flathub style guide.
3. Run the lint commands above against that folder, and build it once.
4. Fork `flathub/flathub` on GitHub with "Copy the master branch only" unchecked.
5. ```bash
   git clone --branch=new-pr git@github.com:<you>/flathub.git && cd flathub
   git checkout -b add-io.helv.Hearth new-pr
   cp /tmp/io.helv.Hearth/* .
   git add . && git commit -m "Add io.helv.Hearth" && git push -u origin add-io.helv.Hearth
   ```
   The folder holds `io.helv.Hearth.yml`, the `python3-*.yaml` files and the `cargo-sources-*.json` files. No source code, no binaries.
6. On github.com open a pull request against the `new-pr` base branch, not `master`. The title is "Add io.helv.Hearth". Keep the template and fill in every box. Disclose the AI use here, naming the parts and the rough extent. Answer reviewers yourself.
7. When the reviewers are satisfied, comment `bot, build` to start a test build. Screenshots do not show in test builds.
8. After approval, a repository `flathub/io.helv.Hearth` is created and an invitation arrives. Two-factor authentication must be on, and the invitation must be accepted within a week.
9. Verify the app ID on the Flathub developer portal. `io.helv.Hearth` is under helv.io, so Flathub asks for a token file at `https://helv.io/.well-known/org.flathub.VerifiedApps.txt`. The site must be reachable over HTTPS, and a page about Hearth that links to the repository helps.

## What only Helvio can do

- Turn on two-factor authentication on the GitHub account that will be invited, and on the `helv-io` organization.
- Decide who the maintainer contact is. Flathub invites a GitHub account to the new repository, and reviewers ask for the maintainer to be reachable there.
- Control `helv.io` and place the verification token file when asked.
- Disclose the AI use and write the pull request by hand, as above.
- Test Hearth in the Flatpak on a real Linux computer with a real iPhone or iPad, including the case where `usbmuxd` is not running at launch.
- Decide whether to ask the Flathub reviewers about the host-dependence rule before investing more.
- Choose the day to submit, once the project has some history.
