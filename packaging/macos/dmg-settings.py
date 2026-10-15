# Layout of Hearth-macos.dmg, read by dmgbuild (https://dmgbuild.readthedocs.io).
#
# The window shows Hearth.app on the left, a shortcut to Applications on the
# right, and an arrow between them, so installing is one drag. dmgbuild writes
# the window layout itself and does not drive Finder, so it works on a CI
# runner with no one logged in.
#
# `defines` comes from dmgbuild's -D option. app is the built bundle.

import os

application = defines.get("app", "dist/Hearth.app")  # noqa: F821
appname = os.path.basename(application)

format = "UDZO"
files = [application]
symlinks = {"Applications": "/Applications"}

background = "builtin-arrow"
window_rect = ((200, 120), (640, 280))
default_view = "icon-view"
icon_size = 128
text_size = 14
icon_locations = {
    appname: (140, 120),
    "Applications": (500, 120),
}
