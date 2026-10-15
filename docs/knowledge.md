# Hearth

What the editor actually does. Read this before changing layout, drag, folders, or the device connection. User-facing setup is in `README.md` and `docs/devices.md`.

The package is `hearth`. The window title is Hearth. `python -m hearth` starts it. QML loads only at startup.

## Device

One iPhone or iPad at a time. `device.presence()` asks usbmux how many are plugged in and returns `none`, `one`, or `many`. It does not return a serial, and nothing in the UI prints one.

The sidebar checks every two seconds. The first time that check sees a single device, and the canvas is not dirty, Hearth reads the layout. A dropout has to show up on two checks in a row before the link state changes, so a one-off miss does not read the phone again. Refresh runs the same check immediately and only reports. It does not replace the canvas.

Read from Device is `controller.pull`. Send to Device is `controller.push`, and it asks first. The confirm text says that gaps on the canvas close on send, because the phone's icon list has no empty cells. Do not block the send.

`_connect` pairs if it has to (`autopair=True`) and passes the single serial into lockdown. Zero devices is "No device is connected". More than one stops the read and the send. Two lockdown sessions at once are unsafe. A presence check is usbmux only. Do not start a second editor while one is already talking to the device.

A read passes ProductType, DeviceClass, the display name, and ProductVersion into the screen picker. No developer disk image. Wallpaper is a separate SpringBoard call because `getHomeScreenWallpaperPNGData` closes the connection. Icons finish on their own connection first. `setIconState` ignores its response. Sleep about two seconds and read the screen back. If bundle ids, page count, or dock order do not match, write the previous layout again. That restore is the safety net. On many unsupervised phones the write is ignored, and has been since around iOS 13. A supervised phone is the case where it is known to stick. Do not claim one path works for every phone.

macOS already has the USB service. Linux needs `usbmuxd`. Windows needs Apple Mobile Device Support (`winget` id `Apple.AppleMobileDeviceSupport`), or Apple Devices from the Store when winget is missing. `hearth/drivers.py` builds those commands from a fixed list. Do not pass typed text into that shell. Flatpak runs the Linux command with `flatpak-spawn --host` and needs `--talk-name=org.freedesktop.Flatpak`. The sandbox does not run its own usbmuxd. The host sockets are `/run/usbmuxd` and `/var/run/usbmuxd`.

## Screens

`hearth/screens.py` picks the grid. `layout.set_screen` is what packing reads when a call omits columns and rows. A default of `None` means the active screen. Do not freeze 4 and 6 as function defaults.

| Family | Grid | Dock | Chassis |
| --- | --- | --- | --- |
| iPhone | 4 × 6 | 4 apps or shortcuts | 390 × 812, island, 15 Pro Max ratio (76.7 × 159.9 mm) |
| iPad | 6 × 5 | up to 15, folders allowed | 744 × 520 stage, no island |

`with_dock` only grows the dock, so extra icons are not hidden. Widgets never go in the dock. Folders are rejected on the iPhone dock and accepted on the iPad dock. The organizer prompt still forbids both, because its schema cannot say an iPad dock folder. Drag can put a folder in the iPad dock anyway.

iOS 26 floor is `iPhone12,*` (iPhone 11 and SE 2nd). `iPhone11,*` is XS and XR and is warned. iPadOS 26 floor is `iPad8,*` and `iPad11,*`. `iPad7,*` is warned. `iPad11,*` is not. An unknown future model opens on its family grid with no warning. Empty product and class is an iPhone with no warning. Anything else uses the iPhone grid plus a warning. A warning does not block the read.

iPad widget spans and portrait-versus-landscape order are still the iPhone stand-in: small 2×2, medium 4×2, large 4×4. A medium widget is four columns on a six-column grid. That is written down as unfinished in `ROADMAP.md`.

## Pages and holes

Pages keep empty cells. Icons and widgets stay where they are placed. They do not pack to the top left. A drop on an empty cell leaves the gap. A drop on an occupied icon shifts only the contiguous occupied run until the next hole.

`_row` and `_col` are editor-only, and only on page items. `strip_positions` runs before a send. `build_view` does not stamp them. `has_holes` is an empty cell strictly before the last item's origin. Trailing slots, and cells beside a widget's lower rows, are not holes.

`_after_target` returns the tile's own origin when the span already reaches the end of the grid. The right-hand bar is hidden when that origin is the insert point. A lone icon already on a page, sent to `at:page:P:end`, stays. Explicit `at:page:P:end` means the first free cell at or after the last survivor's origin.

Between two cells, `floor(x / (cell + gap))` gives the cell, and the gap after a cell belongs to that cell. The right half, and the gap after it, insert after. The left half inserts before. The center 50% of a folder face (25–75% on both axes) returns `into`. Group mode returns `onto` or `into` for the whole tile. The dock and the folder's 3×3 use the same split.

Do not invent GridRow, GridColumn, empty dicts, a placeholder icon type, or an invisible web clip to represent a hole. The wire format for holes is unresolved. Omitting a web clip from the icon state makes the phone put the bookmark back.

## Folders

Folders stay packed. Nine apps to a page. Extra pages hold nine. Empty folder pages are dropped. Reordering inside a folder rechunks dense. `layout.detach` is the document operation that removes an icon. The UI has no Detach button.

A folder with two or more pages shows that count in a red badge on the top right of the tile, on the home screen and in the dock. `pageCount` is the number of icon lists that hold an icon. One page draws nothing. The badge is `PageBadge.qml`.

Click a folder to open it. The tray stays at the bottom of the stage. Opening it does not open the right sidebar and does not detach. One clock animates `dockReveal` and `trayReveal`, 360 ms, OutCubic. The last icon leaving a folder closes it. Pulling the top handle down more than about 56 px closes it. A shorter pull springs back. The handle tracks the pointer in scene coordinates, because the tray moves with the finger and a local `mouse.y` would fight that.

A folder with one icon cannot be reordered inside itself.

## Drag

The picture of an icon starts a move. The name under it pans the page strip. Dock slots have no caption, so the whole slot moves the icon. The word Widget pans. The name on the widget square moves it. Empty canvas pans. A caption inside the folder tray pans folder pages (`passPan: true`). Threshold is 10 px.

The ghost is a `ShaderEffectSource` of the sample at the icon's current pixel size, grabbed at the pointer's offset into that sample. Escape or a right-click cancels. The cancel suppresses the later release, and a new drag does not start while the button is still held.

Holding an icon within about 40–72 px of the left or right edge scrolls that strip. Over the folder pages, the folder strip scrolls. Otherwise the main stage scrolls. The drop target is recomputed as the pages move. Drop geometry does not change.

Qt 6.11 items have no `mapFromScene`. Use `mapFromItem(null, x, y)` and `mapToItem(null, x, y)`.

## Drawing

The stage fits one whole device. Further pages scroll sideways. Minimum window is 1100 × 480. Phone position uses `dockReveal`. Do not add a second Behavior on the phone's width or height.

Widgets are square. The word Widget sits outside the square. The app icon on a widget is faded. Widget extension PNGs are blank, so show the container app's icon.

Rounded corners on the wallpaper and the widget card are a `ShaderEffect` (`roundclip.frag.qsb`) as `layer.effect`. Qt `clip: true` is rectangular. The offscreen software renderer draws a ShaderEffect as nothing. Do not put a Qt5Compat OpacityMask on every icon.

The blue insert pill sits in the center of the gap. Folder bars sit on the cell boundary. Empty phone cells stay transparent unless they are the drop target. Folder empty cells are a small gray square the size of an icon, not the whole cell.

The add-page pill is as tall as the chassis, not the page label, and it lives inside the page strip.

## Versions

Every read and every send writes a plist plus a JSON note. The note holds the reason (`read`, `sent`, `before-send`; `pull`, `pushed` and `before-push` from 0.3.0 and earlier still list and open, and `device.version_name` maps both to the on-screen words), the device field, the time, and the screen (family, columns, rows, dock, product). The screen is not part of the plist. `layout_key` ignores the note and also ignores icon dates and app versions. Neighboring versions with the same key collapse to the earliest. A layout that comes back after a different one is a new run and stays. Collapse runs when the list is rebuilt, so open, read, and send all pass through it.

The icon map in the controller starts empty on every launch. `loadVersion` fills it from the icon cache on disk (`device.restore_icons`), so a version opens with its art and no device attached. An icon with no cached art falls back to the letter tile.

Linux uses the XDG directories. If a `hearth` directory is missing and an `iphone-layout` directory is already there, keep using that directory. Do not create a second one. On macOS the state directory already ends in `versions`, and `version_dir()` adds another. Leave that alone.

Tests that construct a `Controller` must patch `hearth.device.version_dir` to a temporary directory for the whole class. An unpatched controller collapses the real version directory.

## Organize

The default provider is Grok. Chat completions, not the Responses API. Do not hardcode a key. Do not send a web clip URL or other secrets to the model. A proposal stays on the canvas until an explicit send. Apply still builds dense pages. The prompt is told the active grid's columns, rows, dock, and cell count.

The organize field wraps to the scroll view's width, with the horizontal bar forced off. The placeholder is short. The line under the field stays visible while typing.

## Tests and builds

`make test` sets `QT_QPA_PLATFORM=offscreen`. CI has no device. Do not read, send, or restore a device from a test or an unattended session. A send writes the home screen.

Releases are tag `v*`, matching `hearth/__init__.py` and `pyproject.toml`. Windows and macOS are unsigned PyInstaller builds. Linux is the Flatpak `io.helv.Hearth` on the KDE 6.10 runtime, built in the matching `flatpak-github-actions` image. Do not force-move a tag. A failed release gets a new version.

Do not commit pairing records, lockdown keys, home-screen dumps, or anything from a user state directory.
