# -*- mode: python ; coding: utf-8 -*-
"""Onedir Hearth. Windows gets hearth.exe. macOS also gets Hearth.app."""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).resolve().parents[1]
sys.path.insert(0, str(root))
from hearth import __version__
pkg = root / "hearth"
qml = pkg / "qml"

datas = [(str(qml), "qml")]
binaries = []
hiddenimports = ["hearth"]
for name in ("PySide6", "pymobiledevice3"):
    data, binary, hidden = collect_all(name)
    datas += data
    binaries += binary
    hiddenimports += hidden

icon = str(qml / "hearth.ico") if sys.platform == "win32" else None

a = Analysis(
    [str(pkg / "__main__.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="hearth",
    console=False,
    icon=icon,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="hearth",
)
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Hearth.app",
        bundle_identifier="io.helv.Hearth",
        info_plist={
            "CFBundleName": "Hearth",
            "CFBundleDisplayName": "Hearth",
            "CFBundleShortVersionString": __version__,
            "NSHighResolutionCapable": True,
        },
    )
