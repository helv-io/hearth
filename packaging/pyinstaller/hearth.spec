# -*- mode: python ; coding: utf-8 -*-
"""Hearth as one file. Windows gets hearth.exe. macOS gets Hearth.app.

Windows and Linux build a single program that unpacks itself at start. macOS
keeps an app bundle, because a bundle is already one thing to the user.

Only the Qt pieces Hearth imports are carried. PyInstaller's own hooks find
those, so this spec does not collect whole packages. Anything that gets in by
accident is cut by EXCLUDED_MODULES and DROPPED_FILES.
"""

import sys
from pathlib import Path

root = Path(SPECPATH).resolve().parents[1]
sys.path.insert(0, str(root))
from hearth import __version__

pkg = root / "hearth"
qml = pkg / "qml"
frozen_onefile = sys.platform != "darwin"

# Qt and Python parts that Hearth never touches.
EXCLUDED_MODULES = [
    "tkinter",
    "IPython",
    "jedi",
    "parso",
    "pytest",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtSpatialAudio",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras",
    "PySide6.QtQuick3D",
    "PySide6.QtCharts",
    "PySide6.QtGraphs",
    "PySide6.QtGraphsWidgets",
    "PySide6.QtDataVisualization",
    "PySide6.QtLocation",
    "PySide6.QtPositioning",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSerialBus",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtStateMachine",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtTextToSpeech",
    "PySide6.QtVirtualKeyboard",
    "PySide6.QtHttpServer",
    "PySide6.QtNetworkAuth",
    "PySide6.QtUiTools",
    "PySide6.QtXml",
]

# Paths, as they sit inside the bundle, that are left out. Lower case.
DROPPED_FILES = (
    "pyside6/translations/",
    "pyside6/qt/translations/",
    "pyside6/include/",
    "pyside6/typesystems/",
    "pyside6/glue/",
    "pyside6/scripts/",
    "pyside6/metatypes/",
    "pyside6/resources/",
    "pyside6/qt/resources/",
    "pyside6/opengl32sw.dll",
    "pyside6/qt/bin/opengl32sw.dll",
    # Quick Controls styles other than Basic, which is the one Hearth sets.
    "quickcontrols2/fusion",
    "quickcontrols2/imagine",
    "quickcontrols2/material",
    "quickcontrols2/universal",
    "quickcontrols2/fluentwinui3",
    "quickcontrols2/windows",
    "quickcontrols2/macos",
    "quickcontrols2/ios",
    "quickcontrols2/designer",
    "quickstylekit",
    "qtquick/controls/fusion/",
    "qtquick/controls/imagine/",
    "qtquick/controls/material/",
    "qtquick/controls/universal/",
    "qtquick/controls/fluentwinui3/",
    "qtquick/controls/windows/",
    "qtquick/controls/macos/",
    "qtquick/controls/ios/",
    "qtquick/controls/designer/",
    "qtquick/nativestyle/",
    "qtquick/designer/",
    "qtquick/dialogs/",
    "qtquick/tooltips/",
    "qtquick/virtualkeyboard/",
    "qtquick/scene2d/",
    "qtquick/scene3d/",
    "qtquick/particles/",
    "qtquick/localstorage/",
    "qtquick/xmllistmodel/",
    "qtquick/pdf/",
    "qtquick3d/",
    "qt5compat/",
    "qtquick/vectorimage/",
    "qtquick/timeline/",
    "qtquick/tools/",
    "qt/labs/",
    "qtqml/statemachine/",
    "qtqml/xmllistmodel/",
    "qtmultimedia/",
    "qtwebengine/",
    "qtcharts/",
    "qtgraphs/",
    "qtlocation/",
    "qtpositioning/",
    "qtsensors/",
    "qt3d/",
    "qtwebchannel/",
    "qtwebsockets/",
    "qtdatavisualization/",
    "qtremoteobjects/",
    "qtscxml/",
    "qttest/",
    "qtnetworkauth/",
    "qtvirtualkeyboard/",
)

# Programs and libraries that ship in PySide6 and are only for developers.
DROPPED_NAMES = (
    "qmlls", "qmlformat", "qmllint", "qmlcachegen", "qmltyperegistrar",
    "qmlimportscanner", "qmlscene", "qmltestrunner", "qmlplugindump",
    "assistant", "designer", "linguist", "lupdate", "lrelease", "rcc",
    "uic", "balsam", "balsamui", "svgtoqml", "qsb", "qtdiag", "qtpaths",
    "qdbus", "qdbusviewer", "qdoc", "lconvert",
)


# Qt libraries, plugins and bindings Hearth does not use, by part of the file
# name. Qt6 and the lower-case name make these match on every platform.
DROPPED_PARTS = (
    "webengine", "qt63d", "qt6quick3d", "qt6charts", "qt6datavisualization",
    "qt6graphs", "qt6location", "qt6multimedia", "qt6pdf", "qt6positioning",
    "qt6remoteobjects", "qt6scxml", "qt6sensors", "qt6sql", "qt6statemachine",
    "qt6test", "qt6quicktest", "qt6texttospeech", "qt6virtualkeyboard",
    "qt6wayland", "qt6webchannel", "qt6websockets", "qt6webview",
    "qt6designer", "qt6help", "qt6labs", "qt6quickdialogs", "qt6quickparticles",
    "qt6quicktimeline", "qt6quickvectorimage", "qt6qmllocalstorage",
    "qt6qmlxmllistmodel", "qt6qmldesignsupport", "qt6spatialaudio",
    "qt6eglfs", "qt6wlshell", "qt6quickcontrols2native",
    "qt6quickcontrols2fusion", "qt6quickcontrols2imagine",
    "qt6quickcontrols2material", "qt6quickcontrols2universal",
    "qt6quickcontrols2fluentwinui3", "qt6quickcontrols2windows",
    "qt6quickcontrols2macos", "qt6quickcontrols2ios",
    "qtquick3d", "qtmultimedia", "qtpdf", "qtwebengine", "qtcharts",
    "qtsql", "qttest", "qtdesigner", "qtlocation", "qtpositioning",
    "qtsensors", "qtremoteobjects", "qtscxml", "qtstatemachine",
    "qtwebchannel", "qtwebsockets", "qtbluetooth", "qtnfc", "qtserial",
    "qtuitools", "qthelp", "qttexttospeech", "qtvirtualkeyboard",
    "qthttpserver", "qtnetworkauth", "qtgraphs", "qtdatavisualization",
    "qt3d", "qtspatialaudio", "qtconcurrent",
)
DROPPED_PLUGIN_DIRS = (
    "plugins/qmltooling/", "plugins/egldeviceintegrations/",
    "plugins/wayland-", "plugins/generic/", "plugins/networkinformation/",
    "plugins/tls/", "plugins/multimedia/", "plugins/sqldrivers/",
    "plugins/designer/", "plugins/position/", "plugins/sensors/",
    "plugins/geoservices/", "plugins/texttospeech/", "plugins/webview/",
    "plugins/renderers/", "plugins/sceneparsers/", "plugins/geometryloaders/",
    "plugins/qmllint/", "plugins/qmlls/", "plugins/scxmldatamodel/",
    "plugins/canbus/", "plugins/assetimporters/", "plugins/renderplugins/",
)


def wanted(dest):
    path = str(dest).replace("\\", "/").lower()
    if any(drop in path for drop in DROPPED_FILES):
        return False
    base = path.rsplit("/", 1)[-1]
    if "pyside6/" in path:
        if any(part in base for part in DROPPED_PARTS):
            return False
        if any(folder in path for folder in DROPPED_PLUGIN_DIRS):
            return False
    if base.endswith((".pdb", ".debug", ".lib", ".a", ".h", ".hpp", ".prl", ".pyi", ".qmltypes")):
        return False
    stem, dot, ext = base.rpartition(".")
    if not dot:
        stem, ext = base, ""
    if "pyside6/" in path and stem in DROPPED_NAMES and ext in ("", "exe"):
        return False
    return True


datas = [(str(qml), "qml")]

a = Analysis(
    [str(pkg / "__main__.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=["hearth"],
    excludes=EXCLUDED_MODULES,
    noarchive=False,
)
a.datas = [item for item in a.datas if wanted(item[0])]
a.binaries = [item for item in a.binaries if wanted(item[0])]

pyz = PYZ(a.pure)

if frozen_onefile:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="hearth",
        console=False,
        icon=str(qml / "hearth.ico") if sys.platform == "win32" else None,
        upx=False,
        strip=False,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="hearth",
        console=False,
        upx=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name="hearth", upx=False)
    # The app's icon in Finder, the Dock and the disk image. Without one macOS shows
    # the generic script icon. packaging/macos/make-icns.sh builds this file from
    # packaging/macos/icon-1024.png, and macos.yml runs it before PyInstaller.
    icns = root / "packaging" / "macos" / "Hearth.icns"
    if not icns.is_file():
        raise SystemExit(f"{icns} is missing. Run packaging/macos/make-icns.sh first.")
    app = BUNDLE(
        coll,
        name="Hearth.app",
        icon=str(icns),
        bundle_identifier="io.helv.Hearth",
        info_plist={
            "CFBundleIconFile": icns.name,
            "CFBundleName": "Hearth",
            "CFBundleDisplayName": "Hearth",
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "NSHighResolutionCapable": True,
            # macOS asks before an app looks for devices on the home network.
            "NSLocalNetworkUsageDescription": "Hearth looks for your paired iPhone on your home network.",
            "NSBonjourServices": ["_apple-mobdev2._tcp"],
        },
    )
