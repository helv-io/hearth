"""Launch Hearth."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from hearth import __version__
from hearth.controller import Controller
from hearth.paths import resource_dir


def _say(text: str, report: str = "") -> None:
    """Print, or write to a file. A windowed build has no console to print to."""
    if report:
        Path(report).write_text(text, encoding="utf-8")
    elif sys.stdout is not None:
        sys.stdout.write(text)


def _unpacked_megabytes() -> int:
    """Size of the folder a one-file build unpacks into, or 0 when not frozen."""
    root = getattr(sys, "_MEIPASS", "")
    if not root:
        return 0
    total = sum(f.stat().st_size for f in Path(root).rglob("*") if f.is_file())
    return round(total / 1e6)


def _rendered(app, window, lines: list[str]) -> bool:
    """Show the window, let it draw, and check that the picture is not blank."""
    window.show()
    loop = QEventLoop()
    QTimer.singleShot(700, loop.quit)
    loop.exec()
    image = window.grabWindow()
    colors = set()
    for x in range(0, image.width(), 7):
        for y in range(0, image.height(), 7):
            colors.add(image.pixel(x, y))
    lines.append(f"picture {image.width()}x{image.height()} colors {len(colors)}")
    return image.width() > 100 and len(colors) > 8


def _selftest(report: str) -> int:
    """Load the window without a device, write what happened, and quit.

    A packaged build has no console, so the result goes to a file. Used by CI.
    """
    lines: list[str] = []
    code = 1
    try:
        QQuickStyle.setStyle("Basic")
        app = QGuiApplication([sys.argv[0]])
        qml = resource_dir("qml") / "Main.qml"
        lines.append(f"qml {qml}")
        # The device code imports these late, so a packaged build must carry them.
        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.services.springboard import SpringBoardServicesService
        from pymobiledevice3.usbmux import list_devices

        lines.append(
            "device code "
            + ("loaded" if all((create_using_usbmux, SpringBoardServicesService, list_devices)) else "missing")
        )
        controller = Controller()
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("controller", controller)
        engine.load(qml.as_uri())
        roots = engine.rootObjects()
        lines.append(f"windows {len(roots)}")
        if roots:
            code = 0 if _rendered(app, roots[0], lines) else 1
        controller.shutdown()
        del engine, app
    except Exception as error:  # report anything, the exit code is what counts
        lines.append(f"error {error!r}")
    lines.append(f"version {__version__}")
    lines.append(f"unpacked {_unpacked_megabytes()} MB")
    lines.append("ok" if code == 0 else "failed")
    _say("\n".join(lines) + "\n", report)
    return code


def main() -> int:
    args = sys.argv[1:]
    if args[:1] == ["--version"]:
        _say(f"hearth {__version__}\n", args[1] if len(args) > 1 else "")
        return 0
    if args[:1] == ["--selftest"]:
        return _selftest(args[1] if len(args) > 1 else "")
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
