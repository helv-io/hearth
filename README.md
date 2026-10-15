# Hearth

Desktop editor for an iPhone or iPad home screen. Linux, Windows, and macOS.

Plug in one unlocked device. Hearth notices it and reads the layout. Rearrange it, then send it back. Every read and every send saves a version you can open with nothing plugged in.

## Screenshots

Sample home screen. The app icons belong to their owners and are shown only as a demonstration.

![The Hearth window with a sample iPhone home screen: two pages of app icons, folders, widgets and a dock, with the saved versions and the Organize panel at the sides.](docs/images/editor.png)

Click a folder and it opens along the bottom. A folder with more than one page shows every page.

![A folder named Social open at the bottom of the window, showing its two pages of apps.](docs/images/folder.png)

Describe the home screen you want and Hearth shows what it would move. Nothing changes until you press Apply.

![The Organize panel with a short request typed in, and a suggestion that puts three apps into one folder, with Apply and Discard buttons.](docs/images/organizer.png)

Every read and every send is saved. Open an older version from the list and the canvas shows it, with its icons.

![The list of saved versions on the left, and an earlier home screen open on the canvas.](docs/images/versions.png)

## Install

Releases: https://github.com/helv-io/hearth/releases/latest

| System | File | Run |
| --- | --- | --- |
| Windows | `Hearth-windows.exe` | Download it and double-click. Nothing to unzip. Unsigned, so Windows warns first: choose More info, then Run anyway. The first start takes a few seconds. |
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

Unlock the device and tap Trust. Hearth checks every two seconds. The first time it sees one device, and the canvas has no unsaved edits, it reads the layout. Refresh looks again and does not replace the canvas. Read from Device and Send to Device are the manual steps.

One device at a time. If two are plugged in, Hearth does not guess which one you mean. It tells you to unplug one. Two devices talking at once could send a layout to the wrong phone.

macOS already has the USB service, the program that lets a computer talk to an iPhone or iPad over a cable. Windows and Linux may not. Hearth checks at startup. When the service is missing or stopped, the sidebar says so and one button sets it up.

| System | What Hearth does |
| --- | --- |
| Linux | Installs the USB service if it is missing, and starts it. You may be asked for your password. |
| Windows | Installs Apple's USB driver if it is missing, and starts it. You may be asked to approve it. If it cannot, the sidebar opens the [Apple Devices](https://apps.microsoft.com/detail/9np83lwlpz9k) page in the Store. |
| macOS | Nothing. |

When the setup works you see nothing more. If it fails, the sidebar says what went wrong in plain words, and you can press the button again.

### If the button fails

The sidebar then shows **Show manual steps**. It opens the exact step and a Copy button. Run it once in a terminal, and on Windows in a terminal opened as administrator.

| System | Step |
| --- | --- |
| Windows, driver missing | `winget install -e --id Apple.AppleMobileDeviceSupport` |
| Windows, driver stopped | `net start "Apple Mobile Device Service"` |
| Linux | The sidebar shows the line for your distro. It installs `usbmuxd` and starts it. |

## Edit

| | iPhone | iPad |
| --- | --- | --- |
| Grid | 4 × 6 | 6 × 5 |
| Dock | 4 apps or shortcuts | up to 15, folders allowed |
| Widgets in the dock | no | no |

Model list and file locations: [docs/devices.md](docs/devices.md).

Pages keep empty cells. Drop an icon on an empty cell and the gap stays. Drop it on the side of another icon and only the icons up to the next gap shift. Send to Device closes gaps, because the device's icon list has no empty cells. The confirm step says so when the canvas has gaps.

Folders stay packed, nine apps to a page. Two or more pages show that count in a red badge on the folder. One page does not.

Drag the icon to move it. Drag the name under it to slide between pages. Hold an icon at the side of the canvas and that page strip scrolls. That works on the home screen and inside the folder drawer. Click a folder to open it along the bottom. Pull the handle down to close it. Escape or a right-click cancels a drag.

## Limits

Many iPhones and iPads ignore a home screen sent from a computer, and have since around iOS 13. A supervised device (one managed by a school, a company, or Apple Configurator) can accept it. After a send, Hearth reads the screen back and puts the previous layout back when the device did not keep the edit.

There is no single path that works on every iPhone.

## Organize

LLM settings start with Grok. Sign in with Grok opens a browser code. A saved API key still works, and `XAI_API_KEY` is used for Grok when nothing else is saved. The key and the sign-in tokens stay in the user config directory.

Other providers: OpenAI, Anthropic, Google Gemini, Mistral, DeepSeek, Groq, OpenRouter, Ollama, LM Studio, and a custom OpenAI-compatible endpoint. Anthropic uses its Messages API. The rest use chat completions.

The model proposes a layout. Apply puts it on the canvas. Send to Device is a separate step, and it asks first.

## License

GPL-3.0-or-later. The text is in `LICENSE`. pymobiledevice3, which Hearth imports, uses the same license.
