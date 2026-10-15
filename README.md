# Hearth

Desktop editor for an iPhone or iPad home screen. Linux, Windows, and macOS.

Plug in one unlocked device. Hearth notices it and reads the layout. Rearrange it, then send it back. Shortcuts stay the items that came from the device. Every read and every send saves a version you can open with nothing plugged in.

## Install

Releases: https://github.com/helv-io/hearth/releases/latest

| System | File | Run |
| --- | --- | --- |
| Windows | `Hearth-windows.zip` | Unzip and run `Hearth.exe`. Unsigned. |
| macOS | `Hearth-macos.zip` | Open `Hearth.app`. Unsigned. Gatekeeper will warn. |
| Linux | `hearth.flatpak` | `flatpak install --user hearth.flatpak` |

From source:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/hearth
```

On Windows those paths are `.venv\Scripts\pip` and `.venv\Scripts\hearth`.

```bash
make test
```

Tests never open a device. The Makefile sets `QT_QPA_PLATFORM=offscreen`.

## Connect

Unlock the device and tap Trust. Leave one device plugged in. Hearth checks every two seconds. The first time it sees one device, and the canvas has no unsaved edits, it reads the layout. Refresh looks again and does not replace the canvas. Read from Device and Send to Device are the manual steps.

macOS already has the USB service. Windows and Linux do not. Hearth checks at startup. When the service is missing, the sidebar says so and the button installs it.

| System | What is missing | What the button does |
| --- | --- | --- |
| Linux | `usbmuxd` | Installs it with the distro package manager and starts it. Password prompt via `pkexec`. |
| Linux | `usbmuxd` is installed, socket is down | Starts it. |
| Linux Flatpak | same | Runs that command on the host. |
| Windows | Apple Mobile Device Support | `winget install -e --id Apple.AppleMobileDeviceSupport` |
| Windows | winget is missing | Opens [Apple Devices](https://apps.microsoft.com/detail/9np83lwlpz9k) in the Store. iTunes from Apple installs the same driver. |
| Windows | service is stopped | Starts Apple Mobile Device Service. |
| macOS | nothing | No button. |

A developer disk image is not required.

The sidebar shows the command Hearth is about to run. If the button cannot, paste that command in a terminal on the host.

## Edit

| | iPhone | iPad |
| --- | --- | --- |
| Grid | 4 × 6 | 6 × 5 |
| Dock | 4 apps or shortcuts | up to 15, folders allowed |
| Widgets in the dock | no | no |

Model list and file locations: [docs/devices.md](docs/devices.md).

Pages keep empty cells. Drop an icon on an empty cell and the gap stays. Drop it on the side of another icon and only the icons up to the next gap shift. A push closes gaps, because the device's icon list has no empty cells. The confirm step says so when the canvas has gaps.

Folders stay packed, nine apps to a page. Two or more pages show that count in a red badge on the folder. One page does not.

Drag the icon to move it. Drag the name under it to slide between pages. Hold an icon at the side of the canvas and that page strip scrolls. That works on the home screen and inside the folder drawer. Click a folder to open it along the bottom. Pull the handle down to close it. Escape or a right-click cancels a drag.

## Limits

`setIconState` is ignored on many unsupervised devices, and has been since around iOS 13. A supervised device can accept it. Hearth reads the screen back after a push and restores the previous layout when the device does not keep the edit.

There is no single path that works on every iPhone.

## Organize

LLM settings start with Grok. Sign in with Grok opens a browser code. A saved API key still works, and `XAI_API_KEY` is used for Grok when nothing else is saved. The key and the sign-in tokens stay in the user config directory.

Other providers: OpenAI, Anthropic, Google Gemini, Mistral, DeepSeek, Groq, OpenRouter, Ollama, LM Studio, and a custom OpenAI-compatible endpoint. Anthropic uses its Messages API. The rest use chat completions.

The model proposes a layout. Apply puts it on the canvas. Send to Device is a separate step, and it asks first.

## License

GPL-3.0-or-later. The text is in `LICENSE`. pymobiledevice3, which Hearth imports, uses the same license.
