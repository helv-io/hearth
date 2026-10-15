# Working on Hearth

Hearth is a PySide6 app. The package is `hearth`. The console scripts are `hearth` and `iphone-layout`. The version lives in `hearth/__init__.py` and `pyproject.toml`, and the newest `<release>` in `packaging/linux/io.helv.Hearth.metainfo.xml` must match it. The PyInstaller spec reads it from the package. `tests/test_version.py` checks all of them and the changelog.

## Checks

```bash
make test
```

`make test` sets `QT_QPA_PLATFORM=offscreen`. Run that before a commit. A QML change is loaded only at startup, so a running `python -m hearth` does not see it.

Do not point tests at the real version directory. `Controller()` calls `list_versions()`, which collapses neighbor files. Patch `hearth.device.version_dir` to a temporary directory for the whole test class.

Do not pull, push, or restore a device from a test or an agent session unless the person at the computer asks. A push writes the home screen. Two lockdown connections at once are unsafe. CI has no device.

## Layout

- `hearth/screens.py` chooses the grid. `layout.set_screen` is what packing and hit-testing read when a call omits columns and rows. The iPhone default is 4×6 with a dock of 4. Do not freeze those numbers as function defaults. A default of `None` means the active screen.
- Empty cells on a page stay. `has_holes` is an empty cell strictly before the last item's origin. Trailing space is not a hole. Folders still rechunk into nines. `strip_positions` runs before a push.
- `_after_target` returns the tile's own origin when the span reaches the end of the grid. A lone icon sent to the end of its page stays put.
- The drag picture uses the icon's current pixel size. Escape and right-click cancel, and the later mouse release must not drop. Holding an icon at the left or right edge of the main page strip, or of the folder page strip, scrolls that strip. The folder tray stays docked at the bottom. Pulling its top handle down closes it. There is no detach. A folder with two or more pages shows that count in a red badge on the tile. One page does not.
- `hearth/device.py` lists usbmux devices, pairs when it has to, and passes `ProductType` and `DeviceClass` up. It does not log serials or pairing records.
- `hearth/drivers.py` checks the OS. macOS is ready. Linux installs or starts `usbmuxd` through `pkexec`. Windows installs `Apple.AppleMobileDeviceSupport` with winget, or opens Apple Devices when winget is missing. Flatpak runs the Linux command with `flatpak-spawn --host`. Do not pass typed text into that shell. Text a person reads (headline, detail, button, failure message) names no commands. The exact step lives in `Report.manual`, and the sidebar shows it only after a failure, folded away, with a Copy button.
- `hearth/paths.py` keeps using `iphone-layout` state, config, and cache directories when those exist and `hearth` does not. On macOS the state directory already ends in `versions`, and `version_dir()` adds another. Leave that alone.

## Releases

`.github/workflows/ci.yml` runs the tests. `.github/workflows/release.yml` builds Windows, macOS, and a Flatpak when a `v*` tag is pushed. The tag should match the version, like `v0.3.0`. The release notes are the `CHANGELOG.md` section for that version. Windows and macOS artifacts are unsigned. Do not commit pairing records, lockdown keys, home-screen dumps, or anything from a user state directory.

## Docs

Every user-facing change updates `README.md` and `CHANGELOG.md` in the same commit.

User-facing behavior goes in `README.md` and `docs/`. `docs/knowledge.md` is the accumulated behavior of the editor. Read it before changing layout, drag, folders, or the device connection. `CHANGELOG.md` gets a section for the version you ship. `TODO.md` and `ROADMAP.md` are the open work, not a scratch pad for the current edit.
