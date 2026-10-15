"""Launch Hearth."""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from hearth import __version__
from hearth.controller import Controller
from hearth.paths import resource_dir


def main() -> int:
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Hearth")
    app.setOrganizationName("hearth")
    app.setApplicationVersion(__version__)
    icon = resource_dir("qml") / "hearth.png"
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))
    font = QFont("Noto Sans")
    font.setPixelSize(14)
    app.setFont(font)

    controller = Controller()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    qml = resource_dir("qml") / "Main.qml"
    engine.load(qml.as_uri())
    if not engine.rootObjects():
        return 1
    app.aboutToQuit.connect(controller.shutdown)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
