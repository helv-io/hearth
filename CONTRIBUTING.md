# Contributing

Open an issue or a pull request at [helv-io/hearth](https://github.com/helv-io/hearth).

Run `make test` before you push. The tests use `QT_QPA_PLATFORM=offscreen` and must not talk to a device.

Do not add pairing records, lockdown keys, crash dumps that contain a serial, or a real home-screen plist. Sample icons in tests use `com.example` bundle ids.

Changes to the grid go through `hearth/screens.py` and `layout.set_screen`. iPhone tests assume 4 columns, 6 rows, and a dock of 4 whenever the active screen was not changed. Put the screen back in `tearDown` if a test switches it.

This program is GPL-3.0-or-later. A contribution is offered under that license.

`AGENTS.md` is the map of the tree for a person, or an agent, picking the project up cold.
