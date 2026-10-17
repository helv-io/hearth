import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QGuiApplication

from hearth import device, drivers, wireless
from hearth.controller import Controller
from hearth.wireless import Candidate


def phone(udid, name="Helvio's iPhone", transport="USB"):
    return Candidate(udid, name, transport, serial=udid if transport == "USB" else "")


class ScanTests(unittest.TestCase):
    def test_a_failed_scan_is_an_empty_list(self):
        async def boom(**_):
            raise RuntimeError("connection refused")

        with patch("hearth.wireless.discover", boom):
            self.assertEqual(device.scan(), [])

    def test_a_scan_returns_what_was_found(self):
        async def found(**_):
            return [phone("AAA")]

        with patch("hearth.wireless.discover", found):
            self.assertEqual([item.id for item in device.scan()], ["AAA"])


class _ControllerBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        for target, value in (
            ("hearth.device.version_dir", root),
            ("hearth.wireless.config_dir", root),
            ("hearth.wireless.state_dir", root),
            ("hearth.drivers.status", drivers.Report(False, True, "ready")),
        ):
            patcher = patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.controller = Controller()
        self.reads = []
        self.controller.pull = lambda: self.reads.append(self.controller._active)

    def scan(self, *found, manual=False):
        self.controller._on_scanned(self.controller._scan_gen, list(found), manual)


class OneDeviceTests(_ControllerBase):
    def test_one_device_has_no_selector_and_is_read(self):
        self.scan(phone("AAA"))
        self.assertFalse(self.controller.showDevices)
        self.assertEqual(self.reads, ["AAA"])
        self.assertEqual(self.controller.linkLabel, "Device connected")

    def test_refresh_reports_the_device_and_does_not_read(self):
        self.scan(phone("AAA"), manual=True)
        self.assertEqual(self.reads, [])
        self.assertIsNone(self.controller._job)
        self.assertIn("Found Helvio's iPhone", self.controller._status)
        self.assertFalse(self.controller._error)

    def test_refresh_with_nothing_says_so_plainly(self):
        self.scan(manual=True)
        self.assertTrue(self.controller._error)
        self.assertEqual(self.controller._status, "No device found. Plug one in, or wake it.")

    def test_a_dirty_canvas_is_not_replaced_when_a_device_appears(self):
        self.controller._dirty = True
        self.scan(phone("AAA"))
        self.assertEqual(self.reads, [])
        self.assertTrue(self.controller._found)

    def test_a_one_off_dropout_does_not_arm_another_read(self):
        self.scan(phone("AAA"))
        self.scan()
        self.scan(phone("AAA"))
        self.assertEqual(self.reads, ["AAA"])
        self.assertEqual(len(self.controller._found), 1)

    def test_a_device_that_stays_gone_is_read_again_when_it_returns(self):
        self.scan(phone("AAA"))
        self.scan()
        self.scan()
        self.assertEqual(self.controller._found, [])
        self.scan(phone("AAA"))
        self.assertEqual(self.reads, ["AAA", "AAA"])

    def test_the_same_phone_moving_from_wifi_to_the_cable_is_not_read_again(self):
        self.scan(phone("AAA", transport="Wi-Fi"))
        self.assertEqual(self.controller.devices, ["Helvio's iPhone (Wi-Fi)"])
        self.scan(phone("AAA"))
        self.assertEqual(self.controller.devices, ["Helvio's iPhone"])
        self.assertEqual(self.reads, ["AAA"])


class TwoDevicesTests(_ControllerBase):
    def test_two_devices_show_a_selector_and_never_an_error(self):
        self.scan(phone("AAA"), phone("BBB", "Jaclyn's iPhone", "Wi-Fi"))
        self.assertTrue(self.controller.showDevices)
        self.assertEqual(self.controller.devices, ["Helvio's iPhone", "Jaclyn's iPhone (Wi-Fi)"])
        self.assertFalse(self.controller._error)
        self.assertEqual(self.reads, ["AAA"])

    def test_picking_another_device_reads_it_and_is_remembered(self):
        self.scan(phone("AAA"), phone("BBB", "Jaclyn's iPhone", "Wi-Fi"))
        self.controller.chooseDevice(1)
        self.assertEqual(self.reads, ["AAA", "BBB"])
        self.assertEqual(self.controller.deviceIndex, 1)
        self.assertEqual(wireless.last_device(), "BBB")

    def test_the_last_choice_wins_the_next_time(self):
        wireless.remember("BBB")
        self.scan(phone("AAA"), phone("BBB", "Jaclyn's iPhone", "Wi-Fi"))
        self.assertEqual(self.reads, ["BBB"])
        self.assertEqual(self.controller.deviceIndex, 1)

    def test_a_new_device_does_not_take_over_the_one_in_use(self):
        self.scan(phone("AAA"))
        self.scan(phone("AAA"), phone("BBB", "Jaclyn's iPhone", "Wi-Fi"))
        self.assertTrue(self.controller.showDevices)
        self.assertEqual(self.controller._active, "AAA")
        self.assertEqual(self.reads, ["AAA"])

    def test_a_dirty_canvas_switches_without_reading(self):
        self.scan(phone("AAA"), phone("BBB", "Jaclyn's iPhone", "Wi-Fi"))
        self.controller._dirty = True
        self.controller.chooseDevice(1)
        self.assertEqual(self.reads, ["AAA"])
        self.assertEqual(self.controller._active, "BBB")


class SelectionLossTests(_ControllerBase):
    def test_losing_the_selection_falls_back_to_the_other_device(self):
        both = (phone("AAA"), phone("BBB", "Jaclyn's iPhone", "Wi-Fi"))
        self.scan(*both)
        self.controller.chooseDevice(1)
        self.scan(both[0])
        self.assertEqual(self.controller._active, "BBB")  # one miss is not enough
        self.scan(both[0])
        self.assertEqual(self.controller._active, "AAA")
        self.assertFalse(self.controller.showDevices)
        self.assertEqual(self.reads[-1], "AAA")
        self.assertFalse(self.controller._error)

    def test_losing_every_device_goes_back_to_the_empty_state(self):
        self.scan(phone("AAA"), phone("BBB", "Jaclyn's iPhone", "Wi-Fi"))
        self.scan()
        self.scan()
        self.assertEqual(self.controller._active, "")
        self.assertEqual(self.controller.devices, [])
        self.assertEqual(self.controller.deviceIndex, -1)
        self.assertEqual(self.controller.linkLabel, "Nothing connected yet")
        self.assertFalse(self.controller._error)


class WifiSettingTests(_ControllerBase):
    def test_it_is_on_by_default_and_saved(self):
        self.assertTrue(self.controller.wifiEnabled)
        with patch.object(self.controller, "_start_scan"):
            self.controller.setWifiEnabled(False)
        self.assertFalse(wireless.wifi_enabled())
        self.assertFalse(Controller().wifiEnabled)

    def test_turning_it_off_looks_again(self):
        with patch.object(self.controller, "_start_scan") as scan:
            self.controller.setWifiEnabled(False)
        scan.assert_called_once()


if __name__ == "__main__":
    unittest.main()
