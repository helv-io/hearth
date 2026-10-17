# Changelog

## 0.6.5 - 2026-10-17

Send to Device no longer asks a long question. Most of the time it does not ask at all.

- With no gaps on the canvas, Send goes straight to the phone. There is no pop-up.
- With a gap, a small pop-up appears. The first line is red: Apple closes gaps. The second says: Items move up to fill empty cells. Then Send or Cancel.
- Hearth only knows about a gap you made on the canvas. Apple does not tell Hearth where the empty cells on your phone are, so a layout read from the phone always shows as packed.
- The check lives in one function, so the window and the tests use the same rule. Sending, the backup, the read back and the restore are unchanged.

## 0.6.4 - 2026-10-17

On Linux, the Flatpak now sets up the USB service with one button. Before, it told you to install it yourself.

- The cause: Hearth asks your computer, from inside the Flatpak, which installer it has and whether the USB service is there. It got a good answer, but squashed it onto one line and then read none of it. So it believed your computer had no installer and no USB service, and showed "Hearth cannot set it up on this Linux by itself", with only the manual steps. The same mistake could show the setup card when the service was already running.
- Now the answer is read properly. On Arch, Debian, Fedora and the others Hearth knows, the sidebar shows the button, and the manual steps stay folded below it for when the button fails.
- Hearth also checks that the desktop has a window that can ask for your password. Some setups, such as a bare Arch desktop with a tiling window manager, have none, and the setup would sit waiting with nothing on screen. There Hearth now says it cannot ask for your password and shows the steps to run once, instead of waiting.
- New tests read a made-up Arch, Debian and Fedora computer through the same script the Flatpak uses, and fail on 0.6.3.

## 0.6.3 - 2026-10-17

The Linux app starts again after the USB service is installed. With the service running, the 0.6.2 Flatpak stopped at launch with: bwrap: Can't make symlink at /var/run: existing destination is ../run.

- The cause: the Flatpak asked for the USB socket under two names, /run/usbmuxd and /var/run/usbmuxd. On most systems /var/run is a link to /run. When the socket really exists, the current Flatpak and bubblewrap trip over the second name and refuse to start any app that asks for it. Before the USB service was installed there was no socket, so nothing went wrong.
- Now the Flatpak asks for /run/usbmuxd only. The app still reaches the socket by either name inside its sandbox.
- A new test fails if the Flatpak ever asks for anything under /var/run again. The Flatpak build now also creates a real socket at /run/usbmuxd before it starts the installed app, so the check runs the way it does on a computer with the USB service running.
- Nothing else changes. If you installed 0.6.2 from Flatpak, install this one over it.

## 0.6.2 - 2026-10-17

The Linux app starts again. The 0.6.1 Flatpak did not open at all: it stopped at launch with a message about a missing library, libgssapi_krb5.

- The cause: the Flatpak carried its own copy of Qt, which needs a library that the Linux runtime does not include. That copy changed when a newer PySide6 came out on 8 October, and nothing in the build ever started the app, so the break shipped. The Windows and Mac builds already start the app before they are released.
- Now the Flatpak uses the Qt that matches its runtime, from the PySide6 base app, so the library is not needed and the app is much smaller to download.
- The Flatpak build now installs the file the way a person would and starts it with no screen. If it does not start, the build fails and nothing is released.
- Nothing else changes. If you installed 0.6.1 from Flatpak, install this one over it.

## 0.6.1 - 2026-10-17

Dragging a widget now works from anywhere on it, and you can see where it will land.

- While you drag, every cell the item will cover is outlined: one cell for an app, shortcut or folder, four for a small widget, eight for a medium one, sixteen for a large one. Blue means it fits there. Red means it does not, and Hearth says why when you let go.
- A widget is now placed by its own corner, not by the cell under the pointer. Before, the pointer decided, so a widget only landed well when you dropped it with its top left corner on the spot you wanted. Grab a widget by any part and the outline shows where it will really go.
- A widget held past the right or bottom edge now lands against that edge. Before, it was refused.
- You can leave a gap anywhere by dropping a widget there. Gaps still stay where you leave them, and Send to Device still closes them.
- A new test checks that the outline and the drop agree for every kind of item on every cell, and that nothing overlaps or leaves the grid afterwards.

## 0.6.0 - 2026-10-17

Hearth works over Wi-Fi, and it no longer stops when more than one device shows up.

- Hearth no longer refuses to work when it sees more than one device. This is what happened when the same iPhone was connected by cable and by Wi-Fi sync at once. Now each phone is listed once, and when it is on both, Hearth uses the cable.
- With one device there is nothing to choose and nothing new on screen. With more than one, the device name at the top of the sidebar becomes a list. Pick one and Hearth reads it. Hearth remembers your pick for next time. If the device you are using goes away, Hearth moves to the one that is left, or shows that nothing is connected.
- You can now leave the cable out. Plug a device in once and Hearth lets it be found on your home network. After that it shows up as its name with (Wi-Fi) after it. Hearth only connects to a device you have already paired by cable.
- If Hearth cannot find the device on the network, it says: Can't find your iPhone on this network. Wake it, or plug it in. If the connection drops partway, it says: Lost the connection to your iPhone. Wake it and try again.
- Settings has a new switch, Connect over Wi-Fi. It is on by default. Off means Hearth does not look on your network, does not set devices up for Wi-Fi, and ignores any device that is only on Wi-Fi.
- On Linux, a device you have paired before is found over Wi-Fi even when the USB service is not installed, and Hearth no longer asks you to install it in that case.
- The Mac app now asks for permission to find devices on your network, as macOS requires.
- Hearth keeps a private copy of each pairing in its own folder, readable only by you.
- Hearth now needs pymobiledevice3 11.31 or newer.

## 0.5.6 - 2026-10-17

The old name is gone. This is a cleanup, and nothing changes in how the editor works.

- The old command is gone. Start Hearth with `hearth`.
- The old data folders are gone. Hearth now only uses folders named `hearth` for saved versions, settings and downloaded icons. If an older folder with the previous program name is still on your computer, Hearth does not open it and does not delete it. Your saved versions in it will not show up. To keep them, move the folder's contents into the `hearth` folder.
- Every request Hearth makes now says it comes from Hearth and which version. Before, some said the old name.
- A new test fails if the old name shows up anywhere in the project outside this changelog.

## 0.5.5 - 2026-10-16

Hearth no longer picks a model for you.

- There is no built-in model. Grok is a fine choice, and so are the other providers. After you connect one, Organize shows a Pick a model list, and your choice is remembered. Until you have connected, it shows Connect a provider.
- The list is the provider's own, fetched when Hearth starts and when you save Settings. If you are offline, the last list is still there.
- Reorganize with no model chosen says Pick a model first, or Connect a provider to pick a model. It does not send anything to the provider, so there is no confusing error.
- Changing the provider in Settings clears the model, because a model name belongs to the provider it came from.
- If you already chose a model, nothing changes for you.

## 0.5.4 - 2026-10-15

The Mac app now has its own icon, and updates are easier to find.

- On a Mac, Hearth showed the generic script icon, a snake on a page, in the disk image, Finder and the Dock, because the app had no icon of its own. It now has one, in every size macOS uses, and the disk image uses it too. The icon in the window and Dock while Hearth runs matches it.
- Hearth now looks for a newer version every time it starts, not once a day. It still says nothing when you are offline, and Settings can still turn it off. Skip this version still works.
- Settings has a Check for updates button. It checks right away. If there is a newer version it shows the same card with Open download page, even for a version you skipped. If not, it says You're up to date. If Hearth cannot reach GitHub, it says so and you can try again. Only the button shows it is busy, and the rest of the app stays usable. It works even when the check on startup is off.
- The update card now shows above Settings instead of behind it.

## 0.5.3 - 2026-10-15

Organizing no longer fails just because the model is slow, and you can cancel it.

- The model's answer is now streamed. Hearth gives up only when the model has gone quiet, not when the whole answer takes long. It waits 3 minutes for the first words, which covers a model that thinks first, and 1 minute between words after that. Every piece that arrives starts the wait again. Before, one flat two-minute limit failed any slow model, even one that was still writing. A 10 minute limit on a single answer remains as a safety net.
- The status line shows how many characters have arrived, so a slow answer is visibly alive.
- A failure says where it stopped and for how long, for example "The model did not answer for 3 minutes." or "The model went quiet for 1 minute partway through its answer."
- A provider that cannot stream gets the same request without streaming, with no message.
- Hearth now asks for low reasoning when it organizes, for providers that use chat completions. The job is structured JSON, so low is enough, and models that think first answer sooner. If a provider turns that down, Hearth asks again without it and remembers that for the rest of the run. Anthropic uses its own streaming and has no reasoning setting here.
- Reorganize turns into Cancel while Hearth waits for the model. It stops the request at once, shows "Cancelled." with no error, and leaves the app free. A stopped request cannot post a late answer. Closing the window also stops it right away.
- The answer that cannot be read as a layout now says "The model's answer could not be read as a layout. Try again."
- Loading the model list keeps a short 30 second limit.

## 0.5.2 - 2026-10-15

Cancelling the Grok sign-in no longer breaks the app, and the sidebar is quieter.

- Cancelling the Grok sign-in no longer leaves Hearth stuck. Before, the sign-in waited for the full fifteen minutes with every button greyed out, and there was no way to stop it. Now the button turns into Cancel sign-in while Hearth waits. Cancel, closing Settings, switching to another provider, closing the window, or turning the sign-in down in the browser stops it at once. Nothing is shown as an error for a cancel, and you can start again right away.
- Closing the window during a sign-in no longer risks a crash on the way out.
- Real sign-in problems, such as an expired code or an account that cannot sign in, still show a plain message.
- The sidebar no longer has a paragraph of instructions under the Read from Device and Send to Device buttons. The two gestures that are easy to miss, holding an icon at the side of the canvas to turn pages and pulling the folder handle down to close it, are now short hints that show when you hover. The README describes both. The README screenshots were retaken.

## 0.5.1 - 2026-10-15

Hearth now has a download for Intel Macs.

- macOS has two disk images. `Hearth-macos.dmg` is for Macs with an Apple chip, M1 or newer. `Hearth-macos-intel.dmg` is for Macs with an Intel processor. The readme says how to tell which you have, from About This Mac in the Apple menu. Both need macOS 14.4 or newer. The Mac build now covers Intel too.
- Each Mac image is built and checked on its own kind of Mac. The check confirms the app is built for that kind of Mac and starts it natively, before and after the image is made.
- Requests to a model, to Grok sign-in and to the App Store now use the same bundled certificate list as the update check, so a packaged Mac app does not fail on certificates. The built-in check confirms the list is carried.
- Docs: `docs/packaging.md` describes the two Mac builds and the August 2027 end of GitHub's Intel Mac runners.

## 0.5.0 - 2026-10-15

Hearth tells you when a newer version is out, and the Mac download is a disk image.

- macOS is a disk image, `Hearth-macos.dmg`, instead of a zip. Open it and drag Hearth onto the Applications shortcut in the window. It is still unsigned, so the first open needs extra clicks, and the readme now lists them for newer and older versions of macOS. Right-click and Open, which used to be enough, no longer works on macOS 15 and newer.
- The macOS build was for Macs with Apple silicon, M1 and newer. 0.5.1 adds an Intel one.
- Every macOS build opens its own disk image and starts the app from inside it before anything is published.
- Hearth checks at startup whether a newer version exists. A small card says "Hearth X.Y.Z is available" with Open download page, Not now and Skip this version. It asks GitHub at most once a day and stays quiet when you are offline. Settings has a Check for updates on startup box, on by default. That request is the only thing Hearth sends on its own, and it carries nothing about you or your device.

## 0.4.0 - 2026-10-15

Windows is one small file, and the downloads are about a fifth of their old size.

- Windows is a single `Hearth-windows.exe`. Download it and double-click. There is no zip and no folder beside it. It unpacks itself for a few seconds on each start.
- The Windows file is about 60 MB, down from a 340 MB zip that held an 850 MB folder. The macOS download is about 60 MB, down from 270 MB. Hearth only carries the parts of Qt it uses. The web browser engine, 3D, charts, audio and video, the other window styles and the translations are gone.
- Every Windows and macOS build now starts itself once, with no device attached, and checks that the window draws before anything is published.
- The saved versions list says Read from Device, Sent to Device and Before send, the same words as the buttons. It used to say pull, pushed and before push. Versions you saved earlier keep working and show the new words.
- A saved version opened after Hearth restarts shows its real icons. They used to appear only after a read from the device, so an older version could come up as letter tiles.
- Docs: the README has screenshots of a sample home screen.
- Tests and builds: the Windows and macOS builds are their own workflows, which the release calls, and which also run on `cook/` branches. The Windows build fails if the file grows past a size limit. Details are in `docs/packaging.md`.

## 0.3.0 - 2026-10-15

Hearth notices a device, sets up the USB service for you, and shows folder pages.

- A plugged-in device is noticed on its own, and the layout is read when the canvas has no unsaved edits. Refresh checks again without replacing the canvas.
- Hearth checks at startup that the USB service for iPhones and iPads is there. macOS needs nothing. On Linux and Windows one button installs and starts it for you, and on Windows it can open the Apple Devices page instead.
- A folder with two or more pages shows that count in a red badge. Holding an icon at the edge of a page strip scrolls it, on the home screen and in the folder drawer. Pulling the folder handle down closes the drawer.
- The buttons are Read from Device and Send to Device. Messages and docs no longer say pull or push.
- Two devices at once say to unplug one, and the readme explains why.
- The USB setup speaks plainly. The sidebar and the buttons name no commands: Install USB service, Start USB service, Install USB driver, Start USB driver. A failed setup says what went wrong and offers a retry, and on Windows the Apple Devices page. Only after a failure does a folded Show manual steps appear, with the exact step and a Copy button.
- The note on supervised devices in the readme is in everyday words.
- The readme names the Windows program `hearth.exe`, which is what the build makes.
- On Windows, the driver install and the service checks no longer flash console windows.
- The GitHub Release notes come from this changelog.
- Tests and builds: CI runs on every push to master. The macOS app takes its version from the package. The version test checks the package, `pyproject.toml`, the Linux metainfo, and this changelog.

## 0.2.1 - 2026-10-15

The Flatpak release job runs inside the KDE 6.10 builder image, which is the runtime image published for that action. The 0.2.0 job failed immediately because the plain Ubuntu runner has no `flatpak-builder`.

## 0.2.0 - 2026-10-15

First published release. The program is named Hearth.

- An iPhone uses a 4×6 grid and a dock of 4. An iPad uses the 6×5 grid and a dock of up to 15, folders included. A model older than the current OS still opens, with a warning. An unknown newer model opens on its family grid.
- Connecting accepts the Trust prompt. Two devices at once ask you to unplug one.
- Saved versions remember the screen. Versions written before that open as an iPhone. An existing `iphone-layout` data directory is left in place.
- Windows, macOS, and Linux Flatpak release builds run from a version tag.
- The command is `hearth`. `iphone-layout` still starts it.

## 0.1.0

Local editor only. It was not published. Pages can keep empty cells, folders stay packed, and a push strips those editor coordinates.
