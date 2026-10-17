import itertools
import unittest
from pathlib import Path

from PySide6 import QtQuick  # noqa: F401  registers the picture types

from hearth import layout
from hearth.layout import (
    build_view,
    drop_for,
    footprint_cells,
    has_holes,
    move,
    placement,
    snap_origin,
    span,
)

QML = Path(__file__).resolve().parents[1] / "hearth" / "qml"


def app(name):
    return {"bundleIdentifier": name, "displayIdentifier": name, "displayName": name}


def widget(name, size="small"):
    return {"elementType": "widget", "bundleIdentifier": name, "displayIdentifier": name, "gridSize": size}


def folder(name, *apps):
    return {"listType": "folder", "displayName": name, "iconLists": [list(apps)]}


def covered(state, page=0):
    """Every cell covered on a page, and whether two items share one or one leaves the grid."""
    seen = {}
    bad = False
    columns, rows = layout.active_screen().columns, layout.active_screen().rows
    items = state[page + 1]
    positions = layout._positions_of(items)
    for item in items:
        row, col = positions[id(item)]
        width, height = span(item)
        if col < 0 or row < 0 or col + width > columns or row + height > rows:
            bad = True
        for cell in footprint_cells(row, col, width, height):
            if tuple(cell) in seen:
                bad = True
            seen[tuple(cell)] = item
    return seen, bad


def held(width, height, anchor, hold, wiggle=(0.0, 0.0)):
    """Where the top-left corner is, in cells, when an item is held at `hold` cells inside it
    and the pointer is over cell `anchor + hold`."""
    pointer_row = anchor[0] + hold[0] + 0.5 + wiggle[0]
    pointer_col = anchor[1] + hold[1] + 0.5 + wiggle[1]
    return pointer_col - (hold[1] + 0.5), pointer_row - (hold[0] + 0.5)


class SnapTests(unittest.TestCase):
    def test_the_nearest_cell_wins_and_the_footprint_is_pulled_inside(self):
        self.assertEqual(snap_origin(2, 2, 0.4, 0.6, 4, 6), (1, 0))
        self.assertEqual(snap_origin(2, 2, 3.4, 0, 4, 6), (0, 2))  # past the right edge
        self.assertEqual(snap_origin(2, 2, 0, 9.0, 4, 6), (4, 0))  # past the bottom
        self.assertEqual(snap_origin(4, 2, 2.0, 0, 4, 6), (0, 0))  # a medium widget fills the row
        self.assertEqual(snap_origin(4, 4, 1.0, 5.0, 4, 6), (2, 0))
        self.assertEqual(snap_origin(1, 1, -2.0, -1.0, 4, 6), (0, 0))

    def test_a_widget_lands_the_same_wherever_it_is_held(self):
        state = [[], [widget("w", "small")]]
        for anchor in itertools.product(range(0, 5), range(0, 3)):
            for hold in itertools.product(range(2), range(2)):
                for wiggle in ((-0.3, -0.3), (0.0, 0.0), (0.3, 0.3)):
                    left, top = held(2, 2, anchor, hold, wiggle)
                    got = drop_for(state, "page:0:0", 0, left, top)
                    self.assertEqual(got["target"], f"at:page:0:cell:{anchor[0]}:{anchor[1]}", (anchor, hold, wiggle))
                    self.assertEqual(len(got["cells"]), 4)

    def test_near_the_right_and_bottom_edges_it_lands_against_the_edge(self):
        state = [[], [widget("w", "small")]]
        far = drop_for(state, "page:0:0", 0, 3.4, 5.4)
        self.assertEqual((far["row"], far["col"]), (4, 2))
        self.assertTrue(far["valid"])
        self.assertEqual(sorted(map(tuple, far["cells"])), [(4, 2), (4, 3), (5, 2), (5, 3)])


class FootprintTests(unittest.TestCase):
    def test_every_kind_covers_its_whole_size(self):
        pairs = [(app("a"), 1), (folder("f", app("x")), 1), (widget("s", "small"), 4), (widget("m", "medium"), 8), (widget("l", "large"), 16)]
        for item, count in pairs:
            state = [[], [item]]
            got = placement(state, "page:0:0", "at:page:0:cell:0:0")
            self.assertEqual(len(got["cells"]), count)
            self.assertTrue(got["valid"])

    def test_a_blocked_drop_says_which_cells_and_why_not(self):
        fillers = [app(f"a{i}") for i in range(8)]
        # Page 0 is packed solid: large 4x4, medium 4x2, and eight icons fill all 24 cells.
        state = [[], [widget("l", "large"), widget("m", "medium")] + fillers, [widget("s", "small")]]
        got = placement(state, "page:1:0", "at:page:0:cell:0:0")
        self.assertFalse(got["valid"])
        self.assertEqual(got["reason"], "That page is full.")
        self.assertEqual(len(got["cells"]), 4)
        self.assertEqual(move(state, "page:1:0", "at:page:0:cell:0:0"), "That page is full.")

    def test_the_picture_is_what_the_drop_does(self):
        """For every kind of item dropped on every cell of a mixed page: if the footprint says it works,
        the move puts exactly those cells under the item, and nothing overlaps or leaves the grid."""
        for size in ("small", "medium", "large"):
            for row, col in itertools.product(range(6), range(4)):
                state = [[], [
                    app("a"), app("b"), widget("w1", "small"), app("c"), widget("m1", "medium"), app("d"), app("e"),
                ], [widget("moving", size)]]
                shown = placement(state, "page:1:0", f"at:page:0:cell:{row}:{col}")
                result = move(state, "page:1:0", f"at:page:0:cell:{row}:{col}")
                if not shown["valid"]:
                    self.assertIsNotNone(result, (size, row, col))
                    continue
                self.assertIsNone(result, (size, row, col, result))
                moved = next(item for item in state[1] if item.get("bundleIdentifier") == "moving")
                spots, bad = covered(state)
                self.assertFalse(bad, (size, row, col))
                mine = sorted(cell for cell, owner in spots.items() if owner is moved)
                self.assertEqual(mine, sorted(map(tuple, shown["cells"])), (size, row, col))

    def test_a_small_icon_dropped_on_any_cell_of_a_widget_does_not_overlap_it(self):
        for row, col in itertools.product(range(2), range(2)):
            state = [[], [widget("w", "small"), app("a"), app("b")]]
            target = f"at:page:0:cell:{row}:{col}"
            shown = placement(state, "page:0:2", target)
            self.assertIsNone(move(state, "page:0:2", target))
            _spots, bad = covered(state)
            self.assertFalse(bad)
            self.assertEqual(len(shown["cells"]), 1)

    def test_a_hole_left_by_a_drop_stays(self):
        state = [[], [widget("w", "small"), app("a")]]
        got = drop_for(state, "page:0:0", 0, 0.0, 3.4)
        self.assertEqual(got["target"], "at:page:0:cell:3:0")
        self.assertIsNone(move(state, "page:0:0", got["target"]))
        self.assertTrue(has_holes(state))
        view = build_view(state)
        widget_tile = next(tile for tile in view["pages"][0]["tiles"] if tile["kind"] == "widget")
        self.assertEqual((widget_tile["row"], widget_tile["col"], widget_tile["w"], widget_tile["h"]), (3, 0, 2, 2))

    def test_a_drop_that_is_not_on_a_page_cell_has_no_footprint(self):
        state = [[], [app("a"), folder("f", app("x"))]]
        self.assertEqual(placement(state, "page:0:0", "at:dock:0")["cells"], [])
        self.assertEqual(placement(state, "page:0:0", "into:0:1")["cells"], [])
        self.assertEqual(placement(state, "page:9:9", "at:page:0:cell:0:0")["cells"], [])


class PictureStaysHonestTests(unittest.TestCase):
    """The highlight is drawn from the model's answer. These fail if it goes back to guessing."""

    def test_the_page_draws_the_models_cells(self):
        text = (QML / "PhonePage.qml").read_text(encoding="utf-8")
        self.assertIn("root.footprint.cells", text)
        self.assertNotIn("root.hot === modelData.target", text.split("id: footprintLayer")[0])

    def test_a_wide_item_is_placed_by_its_own_corner(self):
        text = (QML / "Main.qml").read_text(encoding="utf-8")
        self.assertIn("controller.dropFor(", text)
        self.assertIn("controller.footprintFor(", text)


if __name__ == "__main__":
    unittest.main()


class OnScreenTests(unittest.TestCase):
    """Drag a widget in the real window and read what the page paints."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtGui import QGuiApplication

        cls._app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        import tempfile
        from unittest.mock import patch

        from hearth import drivers

        folder_ = tempfile.TemporaryDirectory()
        self.addCleanup(folder_.cleanup)
        root = Path(folder_.name)
        for target, value in (
            ("hearth.device.version_dir", root),
            ("hearth.wireless.config_dir", root),
            ("hearth.wireless.state_dir", root),
            ("hearth.drivers.status", drivers.Report(False, True, "ready")),
            ("hearth.device.scan", []),
        ):
            patcher = patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def window(self, page):
        import shiboken6
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlApplicationEngine

        from hearth.controller import Controller

        controller = Controller()
        controller._replace_state([[], page], dirty=False)
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("controller", controller)
        engine.load(QUrl.fromLocalFile(str(QML / "Main.qml")))
        self.assertTrue(engine.rootObjects())

        def close():
            shiboken6.delete(engine)
            controller.shutdown()

        self.addCleanup(close)
        root = engine.rootObjects()[0]
        self.settle()
        return controller, root

    @staticmethod
    def item(window, name):
        """A named item anywhere on screen, found through the picture tree, which delegates join."""
        todo = [window.property("contentItem")]
        while todo:
            current = todo.pop()
            if current.objectName() == name:
                return current
            todo.extend(current.childItems())
        return None

    def settle(self, seconds=0.3):
        import time

        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self._app.processEvents()
            time.sleep(0.01)

    def test_the_whole_footprint_is_painted_and_the_drop_lands_there(self):
        from PySide6.QtCore import QMetaObject, QPointF, Q_ARG, Qt

        controller, root = self.window([widget("w", "small"), app("a")])
        drag = root.findChild(object, "dragState")
        grid = self.item(root, "grid:0")
        self.assertIsNotNone(drag)
        self.assertIsNotNone(grid)
        stride_x = grid.property("cw") + grid.property("gap")
        stride_y = grid.property("ch") + grid.property("gap")

        def scene(row, col):
            return grid.mapToScene(QPointF((col + 0.5) * stride_x - grid.property("gap") / 2,
                                           (row + 0.5) * stride_y - grid.property("gap") / 2))

        # Hold the widget by its bottom-right cell, and put that cell over row 3, column 3.
        start = scene(0, 0)
        hold_x = stride_x * 1.5
        hold_y = stride_y * 1.5
        QMetaObject.invokeMethod(drag, "begin", Qt.DirectConnection,
                                 Q_ARG("QVariant", "page:0:0"), Q_ARG("QVariant", "W"), Q_ARG("QVariant", "w"), Q_ARG("QVariant", "widget"),
                                 Q_ARG("QVariant", start.x()), Q_ARG("QVariant", start.y()), Q_ARG("QVariant", None),
                                 Q_ARG("QVariant", hold_x), Q_ARG("QVariant", hold_y))
        point = scene(3, 3)
        QMetaObject.invokeMethod(drag, "move", Qt.DirectConnection, Q_ARG("QVariant", point.x()), Q_ARG("QVariant", point.y()))
        self.settle()
        footprint = root.property("footprint")
        footprint = footprint.toVariant() if hasattr(footprint, "toVariant") else footprint
        # The held corner is cell (3, 3), so the 2 by 2 widget sits on rows 2 and 3, columns 2 and 3.
        self.assertEqual(sorted(map(tuple, footprint["cells"])), [(2, 2), (2, 3), (3, 2), (3, 3)])
        self.assertTrue(footprint["valid"])
        layer = self.item(root, "footprint:0")
        self.assertEqual(len(layer.property("cells")), 4)
        QMetaObject.invokeMethod(drag, "end", Qt.DirectConnection, Q_ARG("QVariant", point.x()), Q_ARG("QVariant", point.y()))
        self.settle()
        tile = next(t for t in controller.layoutView["pages"][0]["tiles"] if t["kind"] == "widget")
        self.assertEqual((tile["row"], tile["col"]), (2, 2))
        left = root.property("footprint")
        left = left.toVariant() if hasattr(left, "toVariant") else left
        self.assertEqual(left or {}, {})

    def test_an_icon_paints_the_one_cell_it_will_take(self):
        from PySide6.QtCore import Q_ARG, QMetaObject, QPointF, Qt

        controller, root = self.window([app("a"), app("b")])
        drag = root.findChild(object, "dragState")
        grid = self.item(root, "grid:0")
        stride_x = grid.property("cw") + grid.property("gap")
        stride_y = grid.property("ch") + grid.property("gap")
        start = grid.mapToScene(QPointF(stride_x * 0.5, stride_y * 0.3))
        QMetaObject.invokeMethod(drag, "begin", Qt.DirectConnection,
                                 Q_ARG("QVariant", "page:0:0"), Q_ARG("QVariant", "A"), Q_ARG("QVariant", "a"), Q_ARG("QVariant", "app"),
                                 Q_ARG("QVariant", start.x()), Q_ARG("QVariant", start.y()), Q_ARG("QVariant", None),
                                 Q_ARG("QVariant", 10.0), Q_ARG("QVariant", 10.0))
        over = grid.mapToScene(QPointF(stride_x * 2.5, stride_y * 3.3))  # an empty cell: row 3, column 2
        QMetaObject.invokeMethod(drag, "move", Qt.DirectConnection, Q_ARG("QVariant", over.x()), Q_ARG("QVariant", over.y()))
        self.settle()
        footprint = root.property("footprint")
        footprint = footprint.toVariant() if hasattr(footprint, "toVariant") else footprint
        self.assertEqual([tuple(cell) for cell in footprint["cells"]], [(3, 2)])
        self.assertTrue(footprint["valid"])
        QMetaObject.invokeMethod(drag, "cancel", Qt.DirectConnection)
