# Hearth

What the editor actually does. Read this before changing layout, drag, folders, or the device connection. User-facing setup is in `README.md` and `docs/devices.md`.

The package is `hearth`. The window title is Hearth. `python -m hearth` starts it. QML loads only at startup.

## Device

One iPhone or iPad at a time, picked from a list when there is more than one. `hearth/wireless.py` is the one place that finds devices (`discover`) and opens one (`connect`). `discover` merges the USB service's list (cable, and on some systems Wi-Fi entries) with a look on the home network for paired devices, and keeps one row per UDID. A cable beats the USB service's network entry, which beats a name found on the network. With Wi-Fi off, only cable rows exist and the network is never asked. A network look takes about two seconds, so its answer is reused for eight. Refresh asks fresh. Nothing in the UI prints a serial.

The sidebar checks every two seconds. A device that appears is picked up on the first sighting. A device that goes missing has to be missing on two checks in a row, so a one-off miss does not read the phone again. The device in use stays in use when another appears. If it goes away, the last one chosen is next, then the first row. The first read of a newly active device happens once, and only when the canvas is not dirty. A device that fails to read is not retried every two seconds, only when it goes away and comes back. Picking from the list reads that device, unless the canvas has edits, in which case it only switches. Refresh runs the same check immediately and only reports.

Read from Device is `controller.pull`. Send to Device is `controller.push`, and it asks first. Both go to the active device. The confirm text says that gaps on the canvas close on send, because the phone's icon list has no empty cells. Do not block the send.

`wireless.connect` is the only way in. A cable connection pairs if it has to (`autopair=True`), then, with Wi-Fi on, switches on the device's Wi-Fi sync setting (errors ignored) and copies the pairing record into Hearth's own `pairing` folder, mode 0600 in a 0700 folder. A Wi-Fi connection never pairs (`autopair=False`). A Wi-Fi device that does not answer raises `CantFind`, and a connection that drops mid-read or mid-send raises `Lost`. Both carry the plain sentence the person sees. `wireless.Heartbeat` wraps every read and send: a device on Wi-Fi closes its connections unless something answers its pings, and answering costs nothing on a cable. If the heartbeat cannot start, the work goes ahead without it. Two lockdown sessions at once are unsafe. Do not start a second editor while one is already talking to the device. The Linux driver check does not block when the USB service is missing but a stored pairing exists. The Mac app needs `NSLocalNetworkUsageDescription` and `NSBonjourServices` (`_apple-mobdev2._tcp`) in its Info.plist, or macOS will not let it look.

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

Linux uses the XDG directories, and every directory is named `hearth`. On macOS the state directory already ends in `versions`, and `version_dir()` adds another. Leave that alone.

Tests that construct a `Controller` must patch `hearth.device.version_dir` to a temporary directory for the whole class. An unpatched controller collapses the real version directory.

## Organize

The default provider is Grok. There is no default model: `settings.load()["model"]` is empty until the person picks one, and `Controller.modelNeed` says whether to pick or connect first. `propose` refuses before any request. The last model list per endpoint is kept in the cache folder (`settings.last_models`) and refreshed silently at start and after saving or signing in. Chat completions, not the Responses API. Do not hardcode a key. Do not send a web clip URL or other secrets to the model. A proposal stays on the canvas until an explicit send. Apply still builds dense pages. The prompt is told the active grid's columns, rows, dock, and cell count.

The model call (`ai.organize`) streams server-sent events and times out only on silence. `ai.Limits` holds the three numbers: 180 s before the first word, 60 s between words after it, and a 600 s cap on one answer. A `_Watch` thread shuts the socket when a limit is hit or the cancel flag is set, which makes the blocked read return, and then explains why in plain words. The first-word wait is also the `urlopen` timeout, so a server that sends nothing at all, not even headers, fails at 180 s, and a cancel during that wait only takes effect when it ends. Reasoning text and keep-alive lines reset the clock but are not part of the answer. A reply that is not an event stream is read as normal JSON, so a server that ignores `stream` works. A 400 or 422 drops one extra at a time: `reasoning_effort` when the error mentions reasoning or effort, `stream` when it mentions stream, then `response_format`. Dropped effort and stream are remembered per endpoint and model until the app closes (`ai.forget_refusals` clears it, for tests). Nothing matches model names. `Controller.cancelOrganize` follows the Grok sign-in cancel: the job is retired, the app is free at once, and `_current` keeps a retired worker from posting. List models stays a plain request with `ai.LIST_TIMEOUT`.

The organize field wraps to the scroll view's width, with the horizontal bar forced off. The placeholder is short. The line under the field stays visible while typing.

## Tests and builds

`make test` sets `QT_QPA_PLATFORM=offscreen`. CI has no device. Do not read, send, or restore a device from a test or an unattended session. A send writes the home screen.

Releases are tag `v*`, matching `hearth/__init__.py` and `pyproject.toml`. Windows and macOS are unsigned PyInstaller builds. macOS ships two separate DMGs, `Hearth-macos.dmg` (arm64, no tag) and `Hearth-macos-intel.dmg` (x86_64), each built and tested on a native runner, never universal2. Mac dependencies are wheels only, because cryptography 50 has no Intel Mac wheel. Linux is the Flatpak `io.helv.Hearth` on the KDE 6.10 runtime, built in the matching `flatpak-github-actions` image. Do not force-move a tag. A failed release gets a new version.

Do not commit pairing records, lockdown keys, home-screen dumps, or anything from a user state directory.
