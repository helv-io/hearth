# Devices

Hearth talks to one iPhone or iPad through usbmuxd. Unlock the device and tap Trust. A developer disk image is not used.

If two devices are listed, pull and push stop and ask you to leave one plugged in. The serial is not shown.

## Grids

| Family | Columns | Rows | Dock | Chassis in the editor |
| --- | --- | --- | --- | --- |
| iPhone | 4 | 6 | 4 apps or shortcuts | 390 × 812, with the island |
| iPad | 6 | 5 | up to 15, folders allowed | 744 × 520, no island |

The iPhone numbers match the current home screen, including phones that only change the label size. The iPad numbers are the classic More grid. Bigger icons, and a portrait grid that swaps the counts, are not selected yet. See `ROADMAP.md`.

The dock Hearth edits is the pinned side. Recent apps on an iPad are chosen by the system and are not part of the icon list.

A widget keeps the iPhone spans: small 2×2, medium 4×2, large 4×4. That is a stand-in on iPad until a captured icon state shows otherwise.

## Which models

iOS 26 runs on iPhone 11 and later, including iPhone SE (2nd generation). In product-type numbers that floor is `iPhone12,*`. `iPhone11,*` is XS and XR.

iPadOS 26 runs on the 2018 iPad Pros (`iPad8,*`) and later, and on iPad Air (3rd), iPad (8th), and iPad mini (5th), which use `iPad11,*` and above. `iPad7,*` and older, including the 7th-generation iPad, are out of support.

An older model still opens, and the sidebar says so. A push may be ignored. An unrecognized future `iPhone*` or `iPad*` model opens on that family's grid. Anything else is shown on the iPhone grid with a warning.

## Versions

A saved version stores the family, columns, rows, dock size, and product type in the JSON note next to the plist. Notes written before that field existed open as an iPhone.

The plist is the layout. The note is not. Two plists that differ only by icon date or app version still count as one configuration.

## Where files go

Linux uses the XDG directories. macOS uses Application Support and Caches. Windows uses AppData.

If a `hearth` directory is missing and `iphone-layout` is already there, Hearth keeps using `iphone-layout`. A machine with neither gets `hearth`. Pairing records stay in pymobiledevice3's directory, not in this repo.

## Push

Push sends the icon list without editor row and column fields, so gaps close. Hearth reads the screen back. When the bundle ids, page count, or dock order do not match, it writes the previous layout again. A supervised device is the case where `setIconState` is known to stick. An unsupervised device often ignores it. The restore is the safety net either way.
