import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hearth import device, layout, screens
from hearth.layout import move, set_screen


def app(name):
    return {"bundleIdentifier": f"com.example.{name}", "displayName": name}


def folder(name, apps):
    return {
        "listType": "folder",
        "displayName": name,
        "iconLists": [[app(item) for item in apps]],
    }


class ScreenChoiceTests(unittest.TestCase):
    def tearDown(self):
        set_screen(screens.IPHONE)

    def test_current_iphone_uses_four_by_six(self):
        screen = screens.for_device("iPhone17,1", "iPhone")
        self.assertEqual((screen.family, screen.columns, screen.rows, screen.dock), ("iphone", 4, 6, 4))
        self.assertEqual(screen.warning, "")
        self.assertTrue(screen.island)

    def test_iphone_11_is_current_and_xs_is_not(self):
        self.assertEqual(screens.for_device("iPhone12,1", "iPhone").warning, "")
        self.assertEqual(screens.for_device("iPhone12,8", "").warning, "")
        dropped = screens.for_device("iPhone11,8", "iPhone")
        self.assertEqual(dropped.columns, 4)
        self.assertIn("too old", dropped.warning)
        self.assertIn("too old", screens.for_device("iPhone8,4", "iPhone").warning)

    def test_current_ipad_uses_six_by_five(self):
        screen = screens.for_device("iPad14,1", "iPad")
        self.assertEqual((screen.family, screen.columns, screen.rows, screen.dock), ("ipad", 6, 5, 15))
        self.assertFalse(screen.island)
        self.assertEqual(screen.warning, "")
        self.assertEqual(screens.for_device("iPad8,1", "iPad").warning, "")
        self.assertEqual(screens.for_device("iPad11,1", "").family, "ipad")

    def test_old_ipad_still_opens(self):
        dropped = screens.for_device("iPad7,11", "iPad")
        self.assertEqual(dropped.family, "ipad")
        self.assertIn("too old", dropped.warning)

    def test_unknown_future_models_are_allowed(self):
        self.assertEqual(screens.for_device("iPhone99,1", "iPhone").warning, "")
        self.assertEqual(screens.for_device("iPad99,1", "iPad").warning, "")
        self.assertEqual(screens.for_device("", "").family, "iphone")

    def test_a_full_dock_is_not_clipped(self):
        screen = screens.with_dock(screens.IPAD, 18)
        self.assertEqual(screen.dock, 18)
        self.assertEqual(screens.with_dock(screens.IPHONE, 2).dock, 4)

    def test_old_notes_open_as_an_iphone(self):
        self.assertEqual(screens.from_note({}).family, "iphone")
        self.assertEqual(screens.from_note({"reason": "pull"}).dock, 4)
        saved = screens.from_note({"screen": screens.note_fields(screens.IPAD)})
        self.assertEqual(saved.family, "ipad")
        self.assertEqual(saved.columns, 6)

    def test_ipad_page_is_six_columns_and_the_dock_can_hold_a_folder(self):
        set_screen(screens.IPAD)
        icons = [app(str(index)) for index in range(6)]
        state = [[], icons]
        view = layout.build_view(state)
        self.assertEqual(view["columns"], 6)
        self.assertEqual(view["rows"], 5)
        self.assertEqual(view["dockSlots"], 15)
        self.assertEqual(len(view["dock"]), 15)
        self.assertFalse(view["island"])
        self.assertEqual(view["pages"][0]["tiles"][5]["col"], 5)

        state = [[], [folder("Work", ["one"]), app("two")]]
        self.assertIsNone(move(state, "page:0:0", "at:dock:0"))
        self.assertEqual(state[0][0]["displayName"], "Work")

        widget = {
            "elementType": "widget",
            "bundleIdentifier": "com.example.widget",
            "displayName": "Widget",
            "gridSize": "small",
        }
        state = [[], [widget]]
        self.assertIn("dock", move(state, "page:0:0", "at:dock:0"))

    def test_iphone_dock_still_refuses_a_folder(self):
        set_screen(screens.IPHONE)
        state = [[], [folder("Work", ["one"])]]
        self.assertEqual(move(state, "page:0:0", "at:dock:0"), "The dock takes apps and shortcuts.")
        view = layout.build_view([[app("a")], []])
        self.assertEqual(len(view["dock"]), 4)
        self.assertTrue(view["island"])

    def test_a_saved_note_records_the_screen_and_not_the_plist(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with patch("hearth.device.version_dir", return_value=folder):
                path = device.save_version([[app("a")], [app("b")]], "pull", "device", screens.IPAD)
            note = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(note["screen"]["family"], "ipad")
            self.assertEqual(note["screen"]["columns"], 6)
            self.assertEqual(screens.from_note(device.load_note(str(path))).rows, 5)


class StateDirTests(unittest.TestCase):
    def test_a_new_install_uses_hearth(self):
        from hearth import paths

        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"XDG_STATE_HOME": tmp}, clear=False):
                self.assertEqual(paths.state_dir(), Path(tmp) / "hearth")
                self.assertTrue((Path(tmp) / "hearth").is_dir())
