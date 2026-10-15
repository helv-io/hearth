# Hearth

Hearth is a desktop editor for an iPhone or iPad home screen. It runs on Linux, Windows, and macOS.

Plug in one unlocked device, pull the layout over USB, rearrange pages, folders, widgets, and the dock, then push it back. Shortcuts stay the original items from the device. Every pull and every push saves a version, and a saved version opens with nothing plugged in.

## What this is not

Apple shipped a home-screen editor in iTunes until 12.7. Apple Configurator, on a Mac, can still modify a supervised home-screen layout. [iphone-layout-tool](https://github.com/tmad4000/iphone-layout-tool) reads a layout with pymobiledevice3 and pushes it with cfgutil. WiggleGrid edits icons on Windows and does not move widgets.

`setIconState` is ignored on many unsupervised devices, and has been since around iOS 13. A supervised device can accept it. Hearth reads the screen back after a push and restores the previous layout when the device does not keep the edit. There is no single path that works on every iPhone.

A developer disk image is not required.

## Run from source

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/hearth
```

`iphone-layout` is the same program, kept as a command name for one release.

On Windows the virtualenv path is `.venv\Scripts\pip` and `.venv\Scripts\hearth`.

The device has to be unlocked. Tap Trust when the computer asks. Leave one device plugged in. Hearth will not guess between two.

- macOS uses the system USB service.
- Windows needs [Apple Devices](https://apps.microsoft.com/detail/9np83lwlpz9k) or [iTunes from Apple](https://www.apple.com/itunes/download/win64). Either one installs Apple Mobile Device Service.
- Linux needs `usbmuxd` (`apt install usbmuxd`, `dnf install usbmuxd`, or `pacman -S usbmuxd`).

Versions already saved by the earlier `iphone-layout` directory stay where they are. A new install uses a `hearth` directory. See [docs/devices.md](docs/devices.md).

## Releases

Tagged versions build three artifacts:

- Windows and macOS folders from PyInstaller. Those builds are unsigned.
- A Linux Flatpak, `io.helv.Hearth`. It talks to the host `usbmuxd` socket.

The workflow is `.github/workflows/release.yml`. It runs when a `v*` tag is pushed. Install notes are in [docs/packaging.md](docs/packaging.md).

## Editing

Pages keep empty cells. Drop an icon on an empty cell and the gap stays. Drop it on the side of another icon and only the icons up to the next gap shift. A push closes gaps, because the device's icon list has no empty cells. The confirm step says so when the canvas has gaps.

Folders stay packed, nine apps to a page. The dock on an iPhone holds four apps or shortcuts. An iPad dock also holds folders, up to fifteen pinned icons. Widgets stay out of the dock.

Drag the icon to move it. Drag the name under it to slide between pages. Click a folder to open it along the bottom. Escape or a right-click cancels a drag.

## Organize

LLM settings start with Grok. Sign in with Grok opens a browser code. A saved API key still works, and `XAI_API_KEY` is used for Grok when nothing else is saved. The key and the sign-in tokens stay in the user config directory.

The other providers are OpenAI, Anthropic, Google Gemini, Mistral, DeepSeek, Groq, OpenRouter, Ollama, LM Studio, and a custom OpenAI-compatible endpoint. Anthropic uses its Messages API. The rest use chat completions.

The model proposes a layout. Apply puts it on the canvas. Push is a separate step, and it asks first.

## Tests

```bash
make test
```

The tests never open a device. Set `QT_QPA_PLATFORM=offscreen` when there is no display. The Makefile does that.

## License

GPL-3.0-or-later, the same license as pymobiledevice3, which this program imports. The text is in `LICENSE`.
