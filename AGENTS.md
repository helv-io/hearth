# Working on Hearth

Hearth is a PySide6 app. The package is `hearth`. The console scripts are `hearth` and `iphone-layout`. The version lives in `hearth/__init__.py` and `pyproject.toml`. Those two strings must match.

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
- The drag picture uses the icon's current pixel size. Escape and right-click cancel, and the later mouse release must not drop. The folder tray stays docked at the bottom. There is no detach.
- `hearth/device.py` lists usbmux devices, pairs when it has to, and passes `ProductType` and `DeviceClass` up. It does not log serials or pairing records.
- `hearth/paths.py` keeps using `iphone-layout` state, config, and cache directories when those exist and `hearth` does not. On macOS the state directory already ends in `versions`, and `version_dir()` adds another. Leave that alone.

## Releases

`.github/workflows/ci.yml` runs the tests. `.github/workflows/release.yml` builds Windows, macOS, and a Flatpak when a `v*` tag is pushed. The tag should match the version, like `v0.2.1`. Windows and macOS artifacts are unsigned. Do not commit pairing records, lockdown keys, home-screen dumps, or anything from a user state directory.

## Docs

User-facing behavior goes in `README.md` and `docs/`. `CHANGELOG.md` gets a section for the version you ship. `TODO.md` and `ROADMAP.md` are the open work, not a scratch pad for the current edit.
