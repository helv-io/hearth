"""The sidebar is buttons and a list. It carries no explanatory paragraph."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import shiboken6
from PySide6.QtCore import QCoreApplication, QPointF, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem

from hearth import drivers
from hearth.controller import Controller

QML = Path(__file__).resolve().parents[1] / "hearth" / "qml" / "Main.qml"
READY = drivers.Probe(system="Linux", socket_open=True)
REMOVED = ("Drag an icon to move it", "Drop an app on another app", "Pull the folder handle", "slide the pages")


def items(root):
    todo = [root]
    while todo:
        item = todo.pop()
        yield item
        todo.extend(item.childItems())


class SidebarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QGuiApplication.instance() or QGuiApplication([])
        cls._versions = tempfile.TemporaryDirectory()
        cls._patch = patch("hearth.device.version_dir", return_value=Path(cls._versions.name))
        cls._patch.start()

    @classmethod
    def tearDownClass(cls):
        cls._patch.stop()
        cls._versions.cleanup()

    def setUp(self):
        with patch.object(drivers, "live_probe", return_value=READY):
            self.controller = Controller()
        self.engine = QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty("controller", self.controller)
        self.engine.load(QUrl.fromLocalFile(str(QML)))
        self.root = self.engine.rootObjects()[0]
        QCoreApplication.processEvents()
        self.addCleanup(self.close)

    def close(self):
        shiboken6.delete(self.engine)
        self.controller.shutdown()

    def texts(self, group_mode):
        self.root.setProperty("groupMode", group_mode)
        QCoreApplication.processEvents()
        return [
            str(item.property("text"))
            for item in items(self.root.contentItem())
            if item.property("text") is not None and item.property("visible")
        ]

    def test_no_help_paragraph_shows_in_either_mode(self):
        for group_mode in (False, True):
            shown = " ".join(self.texts(group_mode))
            for phrase in REMOVED:
                self.assertNotIn(phrase, shown)

    def test_the_mode_switch_and_the_versions_list_stay_together(self):
        shown = self.texts(False)
        for word in ("Read from Device", "Undo", "Redo", "Move", "Group", "Versions"):
            self.assertIn(word, shown)
        group = next(i for i in items(self.root.contentItem()) if i.property("text") == "Group")
        versions = next(i for i in items(self.root.contentItem()) if i.property("text") == "Versions")
        group_bottom = group.mapToItem(None, QPointF(0, group.height())).y()
        versions_top = versions.mapToItem(None, QPointF(0, 0)).y()
        # One normal row spacing and the switch's own padding. A leftover paragraph would be far larger.
        self.assertLess(versions_top - group_bottom, 40)

    def test_the_two_non_obvious_gestures_are_hints_on_hover_only(self):
        source = QML.read_text(encoding="utf-8")
        self.assertIn("ToolTip.text", source)
        self.assertIn("Hold it at the side of the canvas to turn pages.", source)
        tray = (QML.parent / "FolderTray.qml").read_text(encoding="utf-8")
        self.assertIn("Pull down to close the folder.", tray)


if __name__ == "__main__":
    unittest.main()
