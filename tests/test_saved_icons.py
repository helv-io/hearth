import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QColor, QGuiApplication, QImage

from hearth import device, icons
from hearth.layout import ident


def _app(bundle: str, name: str) -> dict:
    return {"bundleIdentifier": bundle, "displayName": name}


def _png() -> bytes:
    image = QImage(64, 64, QImage.Format.Format_ARGB32)
    image.fill(QColor("#336699"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


class SavedIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        (root / "versions").mkdir()
        (root / "cache").mkdir()
        self._patches = [
            patch("hearth.device.version_dir", return_value=root / "versions"),
            patch("hearth.icons.cache_dir", return_value=root / "cache"),
        ]
        for item in self._patches:
            item.start()

    def tearDown(self):
        for item in self._patches:
            item.stop()
        self._tmp.cleanup()

    def _state(self):
        folder = {"listType": "folder", "displayName": "Tools", "iconLists": [[_app("com.example.inside", "Inside")]]}
        return [[_app("com.example.dock", "Dock")], [_app("com.example.one", "One"), folder]]

    def test_restore_finds_what_an_earlier_read_cached(self):
        state = self._state()
        icons.write_bytes("com.example.one", _png(), "phone")
        icons.write_bytes("com.example.inside", _png(), "store")
        found, missing = device.restore_icons(state)
        self.assertEqual(sorted(found), ["com.example.inside", "com.example.one"])
        self.assertEqual(sorted(job["ident"] for job in missing), ["com.example.dock"])
        self.assertTrue(found["com.example.one"].startswith("file://"))

    def test_nothing_cached_means_nothing_found(self):
        found, missing = device.restore_icons(self._state())
        self.assertEqual(found, {})
        self.assertEqual(len(missing), 3)

    def test_opening_a_saved_version_after_a_restart_shows_its_icons(self):
        from hearth.controller import Controller

        state = self._state()
        path = device.save_version(state, "read", "iPhone")
        icons.write_bytes("com.example.one", _png(), "phone")
        icons.write_bytes("com.example.dock", _png(), "phone")

        restarted = Controller()
        self.assertEqual(restarted.iconUrl("com.example.one"), "")
        before = restarted.iconRev
        restarted.loadVersion(str(path))

        self.assertTrue(restarted.iconUrl("com.example.one").startswith("file://"))
        self.assertTrue(restarted.iconUrl("com.example.dock").startswith("file://"))
        self.assertEqual(restarted.iconUrl("com.example.inside"), "")
        self.assertGreater(restarted.iconRev, before)
        self.assertEqual([ident(item) for item in restarted._state[0]], ["com.example.dock"])
        restarted.shutdown()


class VersionNameTests(unittest.TestCase):
    def test_new_and_old_kinds_read_the_same(self):
        self.assertEqual(device.version_name("read"), "Read from Device")
        self.assertEqual(device.version_name("pull"), "Read from Device")
        self.assertEqual(device.version_name("sent"), "Sent to Device")
        self.assertEqual(device.version_name("pushed"), "Sent to Device")
        self.assertEqual(device.version_name("before-send"), "Before send")
        self.assertEqual(device.version_name("before-push"), "Before send")

    def test_the_list_never_shows_pull_or_push(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with patch("hearth.device.version_dir", return_value=folder):
                for index, reason in enumerate(["pull", "before-push", "pushed", "read", "before-send", "sent"]):
                    path = device.save_version([[_app("d", "D")], [_app(f"a{index}", "A")]], reason)
                labels = [row["label"].lower() for row in device.list_versions()]
        self.assertEqual(len(labels), 6)
        for text in labels:
            self.assertNotIn("pull", text)
            self.assertNotIn("push", text)


if __name__ == "__main__":
    unittest.main()
