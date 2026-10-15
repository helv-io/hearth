# Security

Hearth holds a pairing with the device through pymobiledevice3, in that library's own pairing directory. Those files are secrets. Do not put them in an issue, a commit, or a log pasted into a report.

A home-screen plist names every app and shortcut on the device. Treat a real one as private. The version notes in the user state directory are private too.

Report a vulnerability through a private GitHub security advisory on [helv-io/hearth](https://github.com/helv-io/hearth), or by opening an issue that describes the impact without a pairing record or a layout dump.

Release builds for Windows and macOS are unsigned. Check the tag and the workflow run before you run one.
