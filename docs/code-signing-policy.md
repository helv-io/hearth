# Code signing policy

Free code signing provided by [SignPath.io](https://signpath.io), certificate by [SignPath Foundation](https://signpath.org).

This is the signing policy for the Windows build of Hearth, the program in this repository. Until the first signed release ships, Windows builds are unsigned and Windows SmartScreen will warn about them.

## What gets signed

Only `hearth.exe` and the other Windows program files that GitHub Actions builds from the source code in [helv-io/hearth](https://github.com/helv-io/hearth). Nothing else is signed, and nothing built outside this repository is signed.

- The build runs in GitHub Actions from a version tag, using `.github/workflows/release.yml`. Nobody builds a signed file by hand.
- Every signed file carries the product name `Hearth` and the same product version, which is the version in the tag.
- Libraries that come from other open-source projects, such as Qt and pymobiledevice3, are included as they are. They are not signed with this certificate.
- Hearth is licensed under GPL-3.0-or-later. It contains no proprietary components.

## Team and roles

Hearth has one maintainer, so one person holds every role.

| Role | What it means | Who |
| --- | --- | --- |
| Author | May change the source code without a second review. | [Helvio Pedreschi](https://github.com/Helvio88) |
| Reviewer | Reviews every change that comes from someone who is not an author, such as a pull request from a contributor. | [Helvio Pedreschi](https://github.com/Helvio88) |
| Approver | Approves each signing request. Every release is approved by hand. | [Helvio Pedreschi](https://github.com/Helvio88) |

Members of the [helv-io organization](https://github.com/orgs/helv-io/people) are the only people with write access to the repository. The owners listed there are the approvers. When more people join, this page lists them by role.

Everyone with a role uses multi-factor authentication on GitHub and on SignPath.

## How a release is signed

1. The maintainer pushes a version tag.
2. GitHub Actions runs the tests and builds the Windows program.
3. The build is sent to SignPath from that same workflow run. SignPath checks that it came from this repository and this workflow.
4. The approver reviews the request and approves it by hand.
5. The signed file is attached to the GitHub Release.

A change to `.github/workflows/` or to the build files under `packaging/` is a change to what gets signed, so it gets the closest review.

## Privacy policy

This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.

What that means for Hearth:

- Reading and sending a home screen happens over the USB cable. The layout, the saved versions, and the pairing stay on the computer.
- The Organize feature sends the layout, and the request the user typed, to the AI provider the user chose and signed in to. It does nothing until the user uses it. The provider's own privacy policy applies to what it receives.
- The Install USB driver button on Windows asks winget, or the Microsoft Store, to install Apple's USB driver. It runs only when the user presses it.
- Hearth has no analytics, no tracking, and no automatic update check.

## System changes

Hearth changes nothing on the computer by itself. The one exception is the USB setup button, which installs the USB service (Linux) or Apple's USB driver (Windows) after the user presses it, and the system may ask for approval or a password first.

## Uninstall

- **Hearth:** delete the `hearth` folder (Windows), `Hearth.app` (macOS), or run the Flatpak removal (Linux). Saved versions and settings live in the user's own data folders and can be deleted by hand.
- **Apple's USB driver on Windows:** open Settings, then Apps, then Installed apps, and remove Apple Mobile Device Support.
- **USB service on Linux:** remove the `usbmuxd` package with the system's package manager.

## Reporting a problem

If a file signed under this policy looks wrong, report it through a private security advisory on [helv-io/hearth](https://github.com/helv-io/hearth), or to support@signpath.io. The maintainer will help check it and find the cause.
