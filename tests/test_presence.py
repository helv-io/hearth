import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QGuiApplication

from hearth import device
from hearth.controller import Controller


class PresenceTests(unittest.TestCase):
    def test_counts_are_none_one_or_many(self):
        async def none():
            return []

        async def one():
            return [object()]

        async def many():
            return [object(), object()]

        with patch("hearth.device._listed", none):
            self.assertEqual(device.presence(), "none")
        with patch("hearth.device._listed", one):
            self.assertEqual(device.presence(), "one")
        with patch("hearth.device._listed", many):
            self.assertEqual(device.presence(), "many")

    def test_a_usbmux_failure_is_no_device(self):
        async def boom():
            raise RuntimeError("connection refused")

        with patch("hearth.device._listed", boom):
            self.assertEqual(device.presence(), "none")


class ScanTests(unittest.TestCase):
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

    def test_refresh_reports_one_device_and_does_not_read(self):
        controller = Controller()
        controller._on_scanned(controller._scan_gen, "one", True)
        self.assertEqual(controller._link, "one")
        self.assertIsNone(controller._job)
        self.assertIn("One device", controller._status)

    def test_a_dirty_canvas_is_not_replaced_when_a_device_appears(self):
        controller = Controller()
        controller._dirty = True
        called = []
        controller.pull = lambda: called.append("read")
        controller._on_scanned(0, "one", False)
        self.assertEqual(called, [])
        self.assertEqual(controller._link, "one")

    def test_the_first_sighting_of_one_device_reads(self):
        controller = Controller()
        called = []
        controller.pull = lambda: called.append("read")
        controller._on_scanned(0, "one", False)
        self.assertEqual(called, ["read"])

    def test_a_one_off_dropout_does_not_arm_another_read(self):
        controller = Controller()
        called = []
        controller.pull = lambda: called.append("read")
        controller._link = "one"
        controller._on_scanned(0, "none", False)
        controller._on_scanned(0, "one", False)
        self.assertEqual(called, [])
        self.assertEqual(controller._link, "one")


if __name__ == "__main__":
    unittest.main()
