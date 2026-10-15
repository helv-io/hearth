import unittest
from unittest import mock

from hearth import device, drivers


class WordingTests(unittest.TestCase):
    def test_two_devices_say_to_unplug_one(self):
        text = device.friendly(RuntimeError("More than one device"))
        self.assertIn("Unplug one", text)
        self.assertNotIn("pull", text.lower())

    def test_install_success_names_no_removed_button(self):
        ready = drivers.Report(False, True, "ready", "", "", "", "", (), "")
        needed = drivers.Report(True, False, "install", "", "", "", "", ("x",), "")
        with mock.patch.object(drivers, "status", side_effect=[needed, ready]), \
                mock.patch.object(drivers, "_run", return_value=(0, "")), \
                mock.patch.object(drivers, "_is_windows", return_value=False):
            text = drivers.install()
        self.assertTrue(text.startswith("USB support is ready."))
        self.assertNotIn("pull", text.lower())


if __name__ == "__main__":
    unittest.main()
