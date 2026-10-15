import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QPoint, QPointF, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QMouseEvent
from PySide6.QtQuick import QQuickItem, QQuickView

QML_DIR = Path(__file__).resolve().parents[1] / "hearth" / "qml"


class DragApi(QObject):
    aborted = Signal()

    def __init__(self):
        super().__init__()
        self.events = []
        self.active = False

    @Slot(str, str, str, str, float, float, QObject, float, float)
    def begin(self, source, letter, ident, kind, x, y, sample, hold_x, hold_y):
        self.active = True
        self.events.append((
            "begin",
            source,
            float(sample.property("width") if sample is not None else 0),
            float(sample.property("height") if sample is not None else 0),
            float(hold_x),
            float(hold_y),
        ))

    @Slot(float, float)
    def move(self, x, y):
        self.events.append(("move",))

    @Slot(float, float)
    def end(self, x, y):
        self.events.append(("end",))
        self.cancel()

    @Slot()
    def cancel(self):
        self.events.append(("cancel",))
        self.active = False
        self.aborted.emit()


class DragGestureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.api = DragApi()
        self.view = QQuickView()
        self.view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        self.view.engine().addImportPath(str(QML_DIR))
        self.view.rootContext().setContextProperty("api", self.api)
        harness = Path(__file__).resolve().parent / "drag_harness.qml"
        self.view.setSource(QUrl.fromLocalFile(str(harness)))
        if self.view.status() != QQuickView.Status.Ready:
            errors = "\n".join(error.toString() for error in self.view.errors())
            self.fail(errors)
        self.view.resize(400, 300)
        self.view.show()
        self.app.processEvents()

    def tearDown(self):
        self.view.close()
        self.view.deleteLater()
        self.app.processEvents()

    def _point(self, name, x, y):
        item = self.view.rootObject().findChild(QQuickItem, name)
        self.assertIsNotNone(item, name)
        scene = item.mapToScene(QPointF(x, y))
        return item, QPoint(int(scene.x()), int(scene.y()))

    def _send(self, kind, pos, button, buttons):
        window_pos = QPointF(pos)
        event = QMouseEvent(
            kind,
            window_pos,
            QPointF(self.view.mapToGlobal(pos)),
            button,
            buttons,
            Qt.KeyboardModifier.NoModifier,
        )
        QGuiApplication.sendEvent(self.view, event)
        self.app.processEvents()

    def test_the_drag_picture_keeps_the_icon_size(self):
        icon, start = self._point("icon", 10, 12)
        self.assertEqual(icon.width(), 83)
        self.assertEqual(icon.height(), 47)
        self._send(QMouseEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
        moved = QPoint(start.x() + 24, start.y() + 4)
        self._send(QMouseEvent.Type.MouseMove, moved, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
        begins = [event for event in self.api.events if event[0] == "begin"]
        self.assertEqual(len(begins), 1)
        _, source, width, height, hold_x, hold_y = begins[0]
        self.assertEqual(source, "page:0:0")
        self.assertEqual(width, 83)
        self.assertEqual(height, 47)
        self.assertAlmostEqual(hold_x, 10 + 24, delta=2)
        self.assertAlmostEqual(hold_y, 12 + 4, delta=2)
        self._send(QMouseEvent.Type.MouseButtonRelease, moved, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)
        self.assertIn("end", [event[0] for event in self.api.events])

    def test_a_right_click_cancels_and_the_release_does_not_drop(self):
        _, start = self._point("icon", 20, 20)
        self._send(QMouseEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
        moved = QPoint(start.x() + 30, start.y())
        self._send(QMouseEvent.Type.MouseMove, moved, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
        self.assertIn("begin", [event[0] for event in self.api.events])
        both = Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton
        self._send(QMouseEvent.Type.MouseButtonPress, moved, Qt.MouseButton.RightButton, both)
        self._send(QMouseEvent.Type.MouseMove, QPoint(moved.x() + 16, moved.y()), Qt.MouseButton.NoButton, both)
        self._send(QMouseEvent.Type.MouseButtonRelease, moved, Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton)
        names = [event[0] for event in self.api.events]
        self.assertIn("cancel", names)
        self.assertNotIn("end", names)
        self.assertEqual(names.count("begin"), 1)

    def test_escape_cancels_and_the_release_does_not_drop(self):
        _, start = self._point("dockIcon", 8, 8)
        self._send(QMouseEvent.Type.MouseButtonPress, start, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
        moved = QPoint(start.x() + 18, start.y() + 12)
        self._send(QMouseEvent.Type.MouseMove, moved, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
        begins = [event for event in self.api.events if event[0] == "begin"]
        self.assertEqual(begins[0][2:], (30.0, 30.0, begins[0][4], begins[0][5]))
        self.api.cancel()
        self._send(QMouseEvent.Type.MouseMove, QPoint(moved.x() + 20, moved.y()), Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
        self._send(QMouseEvent.Type.MouseButtonRelease, moved, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)
        names = [event[0] for event in self.api.events]
        self.assertNotIn("end", names)
        self.assertEqual(names.count("begin"), 1)

    def test_the_folder_tray_has_no_detach_control(self):
        tray = (QML_DIR / "FolderTray.qml").read_text(encoding="utf-8")
        main = (QML_DIR / "Main.qml").read_text(encoding="utf-8")
        self.assertNotIn("Detach", tray)
        self.assertNotIn("forceFloat", main)
        self.assertNotIn("detached", main)
        self.assertIn('sequence: "Escape"', main)
        self.assertIn("nudgePages", main)
        self.assertIn("pagesFlick", tray)
        self.assertIn("folderHandle", tray)
        self.assertIn("closeFolder", tray)
        phone = (QML_DIR / "PhonePage.qml").read_text(encoding="utf-8")
        self.assertIn("pageCount", phone)
        self.assertIn("driverCard", main)
        self.assertIn("installDriver", main)
        self.assertIn('placeholderText: "Put games together. Keep the dock."', main)
        self.assertIn("instructionView.availableWidth", main)
        self.assertIn("Write a little or a lot.", main)
        self.assertIn('text: "Read from Device"', main)
        self.assertIn('text: "Send to Device"', main)
        self.assertIn("refreshDevice", main)

    def test_qml_files_compile(self):
        from PySide6.QtQml import QQmlComponent, QQmlEngine

        engine = QQmlEngine()
        for name in ("Main.qml", "PhonePage.qml", "FolderTray.qml", "DragSpot.qml", "IconBadge.qml", "PageBadge.qml"):
            component = QQmlComponent(engine, QUrl.fromLocalFile(str(QML_DIR / name)))
            errors = "\n".join(error.toString() for error in component.errors())
            self.assertEqual(component.status(), QQmlComponent.Status.Ready, f"{name}\n{errors}")


if __name__ == "__main__":
    unittest.main()
