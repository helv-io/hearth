"""Send asks a question only when a gap would close, and the question is short."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import shiboken6
from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from hearth import drivers, layout
from hearth.controller import Controller
from hearth.layout import gaps_before_send, has_holes, move

QML = Path(__file__).resolve().parents[1] / "hearth" / "qml" / "Main.qml"
READY = drivers.Probe(system="Linux", socket_open=True)


def app(name):
    return {"bundleIdentifier": name, "displayIdentifier": name, "displayName": name}


def widget(name, size="small"):
    return {"elementType": "widget", "bundleIdentifier": name, "displayIdentifier": name, "gridSize": size}


class GapRuleTests(unittest.TestCase):
    def test_a_layout_read_from_the_phone_has_no_gap(self):
        page = [app(f"app{n}") for n in range(23)]
        self.assertEqual(gaps_before_send([[app("d")], page]), [])

    def test_a_page_of_widgets_in_order_has_no_gap(self):
        page = [widget("a"), widget("b"), widget("c")]
        self.assertEqual(gaps_before_send([[], page]), [])

    def test_an_empty_state_or_empty_page_has_no_gap(self):
        self.assertEqual(gaps_before_send([[]]), [])
        self.assertEqual(gaps_before_send([[], []]), [])

    def test_space_after_the_last_item_is_not_a_gap(self):
        state = [[], [app("a"), app("b")]]
        self.assertEqual(gaps_before_send(state), [])

    def test_an_icon_dropped_past_an_empty_cell_is_a_gap(self):
        state = [[], [app("a"), app("b")]]
        self.assertIsNone(move(state, "page:0:1", "at:page:0:cell:0:3"))
        self.assertEqual(gaps_before_send(state), [1])
        self.assertTrue(has_holes(state))

    def test_the_gap_names_the_page_it_is_on(self):
        state = [[], [app("a"), app("b")], [app("c"), app("d")]]
        self.assertIsNone(move(state, "page:1:1", "at:page:1:cell:2:2"))
        self.assertEqual(gaps_before_send(state), [2])

    def test_a_widget_dropped_lower_leaves_empty_rows_before_it(self):
        state = [[], [widget("a"), widget("b"), widget("c")]]
        self.assertIsNone(move(state, "page:0:2", "at:page:0:cell:4:2"))
        self.assertEqual(gaps_before_send(state), [1])

    def test_the_cells_a_widget_covers_are_not_gaps(self):
        state = [[], [widget("a", "medium"), app("b"), app("c")]]
        self.assertEqual(gaps_before_send(state), [])

    def test_asking_does_not_change_the_layout(self):
        state = [[], [app("a"), app("b")]]
        move(state, "page:0:1", "at:page:0:cell:0:3")
        before = copy.deepcopy(state)
        gaps_before_send(state)
        self.assertEqual(state, before)


class SendDialogTests(unittest.TestCase):
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

    def send(self, state):
        sent = []
        self.controller._replace_state(state, True)
        with patch.object(self.controller, "push", side_effect=lambda: sent.append(1)):
            self.root.setProperty("confirmOpen", False)
            from PySide6.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(self.root, "trySend", Qt.ConnectionType.DirectConnection)
            QCoreApplication.processEvents()
        return sent, self.root.property("confirmOpen")

    def test_no_gap_sends_straight_away_with_no_dialog(self):
        sent, shown = self.send([[], [app("a"), app("b")]])
        self.assertEqual(sent, [1])
        self.assertFalse(shown)

    def test_a_gap_shows_the_dialog_and_does_not_send_yet(self):
        state = [[], [app("a"), app("b")]]
        move(state, "page:0:1", "at:page:0:cell:0:3")
        sent, shown = self.send(state)
        self.assertEqual(sent, [])
        self.assertTrue(shown)

    def test_the_dialog_is_short_and_blames_apple_in_red(self):
        head = self.root.findChild(object, "gapHeadline")
        line = self.root.findChild(object, "gapLine")
        self.assertEqual(head.property("text"), "Apple closes gaps.")
        self.assertEqual(line.property("text"), "Items move up to fill empty cells.")
        self.assertEqual(head.property("color").name().lower(), "#ff453a")
        self.assertLessEqual(len(head.property("text").split()), 6)

    def test_nothing_sends_while_the_window_is_busy(self):
        self.controller._busy = True
        sent, shown = self.send([[], [app("a")]])
        self.assertEqual((sent, shown), ([], False))

    def test_the_old_long_text_is_gone_everywhere(self):
        root = Path(__file__).resolve().parents[1]
        old = ("Send this layout?", "replaces the home screen", "A backup is saved first", "Sending closes them")
        for path in [*root.joinpath("hearth").rglob("*.qml"), *root.joinpath("hearth").rglob("*.py"),
                     root / "README.md", *root.joinpath("docs").rglob("*.md")]:
            text = path.read_text(encoding="utf-8")
            for phrase in old:
                self.assertNotIn(phrase, text, f"{path.name}: {phrase}")


if __name__ == "__main__":
    unittest.main()
