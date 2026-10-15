# Roadmap

## 0.3

Published editor. One iPhone or iPad, noticed on its own. A 4×6 or 6×5 grid, versions, folder page badges, USB service setup on Linux and Windows, and release builds for Windows, macOS, and Linux Flatpak. This is the current version.

## 0.4

Device picker. iPad widget sizes and page orientation taken from the device instead of assumed. Organizer proposals that understand the iPad dock. A signed macOS build if an Apple developer account is available for the project.

## 0.5

Flathub. A Windows build signed well enough for SmartScreen. A way to keep an intentional gap across a push, if the icon-state format can represent one without inventing placeholder icons.

Hearth will not grow a second layout engine for unsupervised phones that ignore `setIconState`. The honest limit stays in the readme: the push is attempted, the screen is read back, and the previous layout is restored when the device changes it.
