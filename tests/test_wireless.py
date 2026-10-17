import asyncio
import os
import plistlib
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import shiboken6
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from hearth import drivers, wireless
from hearth.controller import Controller
from hearth.wireless import Candidate

QML = Path(__file__).resolve().parents[1] / "hearth" / "qml" / "Main.qml"
SPEC = Path(__file__).resolve().parents[1] / "packaging" / "pyinstaller" / "hearth.spec"


def run(coro):
    return asyncio.run(coro)


class _Folder(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        for target in ("hearth.wireless.config_dir", "hearth.wireless.state_dir"):
            patcher = patch(target, return_value=self.root)
            patcher.start()
            self.addCleanup(patcher.stop)
        wireless._browsed.update(at=0.0, found=[])
        wireless._names.clear()


class DedupeTests(unittest.TestCase):
    def test_the_cable_beats_wifi_for_the_same_phone(self):
        wifi = Candidate("00008110-AAA", "Phone", "Wi-Fi", address="10.0.0.5")
        usb = Candidate("00008110AAA", "Phone", "USB", serial="00008110AAA")
        for order in ([wifi, usb], [usb, wifi]):
            kept = wireless.dedupe(order)
            self.assertEqual(len(kept), 1)
            self.assertEqual(kept[0].transport, "USB")

    def test_the_usb_service_beats_a_name_found_on_the_network(self):
        named = Candidate("AAA", "Phone", "Wi-Fi", address="10.0.0.5")
        muxed = Candidate("AAA", "Phone", "Wi-Fi", serial="AAA")
        self.assertEqual(wireless.dedupe([named, muxed])[0].serial, "AAA")

    def test_different_phones_stay_apart_and_the_cable_comes_first(self):
        kept = wireless.dedupe([
            Candidate("BBB", "Zed", "Wi-Fi", address="10.0.0.6"),
            Candidate("AAA", "Amy", "Wi-Fi", address="10.0.0.5"),
            Candidate("CCC", "Cal", "USB", serial="CCC"),
        ])
        self.assertEqual([item.name for item in kept], ["Cal", "Amy", "Zed"])

    def test_labels_name_wifi_only_phones_and_number_twins(self):
        rows = [
            Candidate("A", "Phone", "USB", serial="A"),
            Candidate("B", "Phone", "USB", serial="B"),
            Candidate("C", "Other", "Wi-Fi", address="x"),
        ]
        self.assertEqual(wireless.labels(rows), ["Phone", "Phone 2", "Other (Wi-Fi)"])


class PickTests(unittest.TestCase):
    rows = [Candidate("AAA", "A", "USB"), Candidate("BBB", "B", "Wi-Fi")]

    def test_the_one_in_use_stays(self):
        self.assertEqual(wireless.pick(self.rows, "AAA", "BBB"), "BBB")

    def test_then_the_last_one_chosen(self):
        self.assertEqual(wireless.pick(self.rows, "BBB", ""), "BBB")

    def test_then_the_first(self):
        self.assertEqual(wireless.pick(self.rows, "ZZZ", "YYY"), "AAA")

    def test_nothing_gives_nothing(self):
        self.assertEqual(wireless.pick([], "AAA", "BBB"), "")


class DiscoverTests(_Folder):
    def usb(self, *rows):
        return patch("hearth.wireless._usbmux", AsyncMock(return_value=list(rows)))

    def test_it_merges_the_cable_and_the_network_by_phone(self):
        usb = Candidate("AAA", "Phone", "USB", serial="AAA")
        net = [Candidate("AAA", "Phone", "Wi-Fi", address="x"), Candidate("BBB", "Other", "Wi-Fi", address="y")]
        with self.usb(usb), patch("hearth.wireless._network", AsyncMock(return_value=net)):
            found = run(wireless.discover(wifi=True))
        self.assertEqual([(item.id, item.transport) for item in found], [("AAA", "USB"), ("BBB", "Wi-Fi")])

    def test_with_wifi_off_the_network_is_never_asked(self):
        usb = Candidate("AAA", "Phone", "USB", serial="AAA")
        ask = AsyncMock(side_effect=AssertionError("looked on the network"))
        with self.usb(usb), patch("hearth.wireless._network", ask):
            found = run(wireless.discover(wifi=False))
        self.assertEqual([item.id for item in found], ["AAA"])
        ask.assert_not_called()

    def test_with_wifi_off_a_usb_service_entry_for_the_network_is_ignored(self):
        listed = [
            SimpleNamespace(serial="AAA", is_usb=True),
            SimpleNamespace(serial="BBB", is_usb=False),
        ]
        with patch("pymobiledevice3.usbmux.list_devices", AsyncMock(return_value=listed)):
            self.assertEqual([item.serial for item in run(wireless._usbmux(False))], ["AAA"])
            self.assertEqual([item.serial for item in run(wireless._usbmux(True))], ["AAA", "BBB"])

    def test_the_setting_decides_when_nothing_is_passed(self):
        ask = AsyncMock(return_value=[Candidate("BBB", "Other", "Wi-Fi", address="y")])
        with self.usb(), patch("hearth.wireless._network", ask):
            self.assertEqual(len(run(wireless.discover())), 1)
            wireless.set_wifi_enabled(False)
            self.assertEqual(run(wireless.discover()), [])
        self.assertEqual(ask.call_count, 1)

    def test_no_usb_service_still_finds_a_phone_on_the_network(self):
        net = [Candidate("BBB", "Other", "Wi-Fi", address="y")]
        with patch("pymobiledevice3.usbmux.list_devices", AsyncMock(side_effect=OSError("no service"))), \
                patch("hearth.wireless._network", AsyncMock(return_value=net)):
            self.assertEqual([item.id for item in run(wireless.discover(wifi=True))], ["BBB"])

    def test_a_fresh_network_answer_is_reused_for_a_moment(self):
        found = [Candidate("BBB", "Other", "Wi-Fi", address="y")]
        browse = AsyncMock(return_value=found)
        with patch("hearth.wireless._browse", browse):
            run(wireless._network(0.1, False))
            run(wireless._network(0.1, False))
            self.assertEqual(browse.call_count, 1)
            run(wireless._network(0.1, True))
            self.assertEqual(browse.call_count, 2)


class SettingTests(_Folder):
    def test_wifi_is_on_by_default_and_the_choice_sticks(self):
        self.assertTrue(wireless.wifi_enabled())
        wireless.set_wifi_enabled(False)
        self.assertFalse(wireless.wifi_enabled())
        wireless.set_wifi_enabled(True)
        self.assertTrue(wireless.wifi_enabled())

    def test_the_last_device_sticks(self):
        self.assertEqual(wireless.last_device(), "")
        wireless.remember("AAA")
        self.assertEqual(wireless.last_device(), "AAA")

    @unittest.skipIf(sys.platform == "win32", "file modes do not apply")
    def test_the_pairing_copy_is_readable_only_by_the_person(self):
        wireless.keep_pair_record("00008110-AAA", {"HostID": "H", "HostPrivateKey": b"secret"})
        files = wireless.stored_records()
        self.assertEqual(len(files), 1)
        self.assertEqual(stat.S_IMODE(os.stat(files[0]).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(files[0].parent).st_mode), 0o700)
        self.assertEqual(plistlib.loads(files[0].read_bytes())["HostID"], "H")

    def test_something_that_is_not_a_pairing_record_is_not_kept(self):
        wireless.keep_pair_record("AAA", None)
        wireless.keep_pair_record("AAA", {"nothing": 1})
        self.assertEqual(wireless.stored_records(), [])


class ConnectTests(_Folder):
    def client(self):
        client = MagicMock()
        client.set_enable_wifi_connections = AsyncMock()
        client.udid = "00008110-AAA"
        client.pair_record = {"HostID": "H"}
        return client

    def test_the_cable_pairs_if_needed_turns_wifi_on_and_keeps_the_record(self):
        client = self.client()
        make = AsyncMock(return_value=client)
        with patch("pymobiledevice3.lockdown.create_using_usbmux", make):
            got = run(wireless.connect(Candidate("AAA", "P", "USB", serial="AAA")))
        self.assertIs(got, client)
        self.assertTrue(make.call_args.kwargs["autopair"])
        self.assertEqual(make.call_args.kwargs["connection_type"], "USB")
        client.set_enable_wifi_connections.assert_awaited_once_with(True)
        self.assertEqual(len(wireless.stored_records()), 1)

    def test_with_wifi_off_the_cable_changes_nothing_on_the_phone_and_keeps_nothing(self):
        wireless.set_wifi_enabled(False)
        client = self.client()
        with patch("pymobiledevice3.lockdown.create_using_usbmux", AsyncMock(return_value=client)):
            run(wireless.connect(Candidate("AAA", "P", "USB", serial="AAA")))
        client.set_enable_wifi_connections.assert_not_called()
        self.assertEqual(wireless.stored_records(), [])

    def test_a_phone_that_refuses_the_wifi_switch_still_connects(self):
        client = self.client()
        client.set_enable_wifi_connections = AsyncMock(side_effect=RuntimeError("no"))
        with patch("pymobiledevice3.lockdown.create_using_usbmux", AsyncMock(return_value=client)):
            self.assertIs(run(wireless.connect(Candidate("AAA", "P", "USB", serial="AAA"))), client)

    def test_wifi_never_pairs(self):
        client = self.client()
        tcp = AsyncMock(return_value=client)
        with patch("pymobiledevice3.lockdown.create_using_tcp", tcp):
            run(wireless.connect(Candidate("AAA", "P", "Wi-Fi", address="10.0.0.5", record={"HostID": "H"})))
        self.assertFalse(tcp.call_args.kwargs["autopair"])
        self.assertEqual(tcp.call_args.args[0], "10.0.0.5")
        client.set_enable_wifi_connections.assert_not_called()

    def test_a_phone_the_usb_service_lists_on_the_network_never_pairs(self):
        mux = AsyncMock(return_value=self.client())
        with patch("pymobiledevice3.lockdown.create_using_usbmux", mux):
            run(wireless.connect(Candidate("AAA", "P", "Wi-Fi", serial="AAA")))
        self.assertFalse(mux.call_args.kwargs["autopair"])
        self.assertEqual(mux.call_args.kwargs["connection_type"], "Network")

    def test_a_phone_that_does_not_answer_says_to_wake_it(self):
        with patch("pymobiledevice3.lockdown.create_using_tcp", AsyncMock(side_effect=OSError("timed out"))):
            with self.assertRaises(wireless.CantFind) as caught:
                run(wireless.connect(Candidate("AAA", "P", "Wi-Fi", address="10.0.0.5")))
        self.assertEqual(str(caught.exception), "Can't find your iPhone on this network. Wake it, or plug it in.")

    def test_a_dropped_connection_is_told_apart_from_a_refusal(self):
        self.assertTrue(wireless.dropped(ConnectionResetError()))
        self.assertTrue(wireless.dropped(RuntimeError("socket closed")))
        self.assertFalse(wireless.dropped(RuntimeError("The phone did not keep that layout.")))


class _Service:
    def __init__(self, marcos=2, fail_first=False):
        self.sent = []
        self.closed = False
        self._queue = asyncio.Queue()
        self._fail_first = fail_first
        for _ in range(marcos):
            self._queue.put_nowait({"Command": "Marco"})

    async def recv_plist(self):
        if self._fail_first:
            raise ConnectionError("gone")
        return await self._queue.get()

    async def send_plist(self, data):
        self.sent.append(data)

    async def close(self):
        self.closed = True


class HeartbeatTests(unittest.TestCase):
    def test_every_marco_gets_a_polo_and_it_stops_cleanly(self):
        async def go():
            service = _Service(marcos=3)
            client = MagicMock()
            client.start_lockdown_service = AsyncMock(return_value=service)
            async with wireless.Heartbeat(client):
                for _ in range(50):
                    await asyncio.sleep(0.01)
                    if len(service.sent) == 3:
                        break
                service._queue.put_nowait({"Command": "Marco"})
                await asyncio.sleep(0.05)
            client.start_lockdown_service.assert_awaited_once_with("com.apple.mobile.heartbeat")
            self.assertEqual(service.sent, [{"Command": "Polo"}] * 4)
            self.assertTrue(service.closed)

        run(go())

    def test_work_goes_ahead_when_it_cannot_start(self):
        async def go():
            service = _Service(fail_first=True)
            client = MagicMock()
            client.start_lockdown_service = AsyncMock(return_value=service)
            async with wireless.Heartbeat(client):
                ran = True
            self.assertTrue(ran)
            self.assertTrue(service.closed)

            client.start_lockdown_service = AsyncMock(side_effect=RuntimeError("no service"))
            async with wireless.Heartbeat(client):
                pass

        run(go())

    def test_a_phone_that_stays_silent_does_not_hold_the_work_up(self):
        async def go():
            service = _Service(marcos=0)
            client = MagicMock()
            client.start_lockdown_service = AsyncMock(return_value=service)
            began = time.monotonic()
            async with wireless.Heartbeat(client, first_wait=0.05):
                pass
            self.assertLess(time.monotonic() - began, 1.0)
            self.assertTrue(service.closed)

        run(go())


class DriverTests(_Folder):
    def test_linux_without_the_usb_service_does_not_block_when_a_pairing_is_stored(self):
        probe = drivers.Probe(system="Linux", stored_pairing=True)
        report = drivers.status(probe)
        self.assertFalse(report.needed)
        self.assertTrue(report.ready)

    def test_linux_without_the_usb_service_and_no_pairing_still_asks(self):
        report = drivers.status(drivers.Probe(system="Linux"))
        self.assertTrue(report.needed)
        self.assertFalse(report.ready)

    def test_the_stored_pairing_counts_only_with_wifi_on(self):
        wireless.keep_pair_record("AAA", {"HostID": "H"})
        self.assertTrue(drivers._has_stored_pairing())
        wireless.set_wifi_enabled(False)
        self.assertFalse(drivers._has_stored_pairing())


class MacPermissionTests(unittest.TestCase):
    def test_the_mac_app_may_look_on_the_home_network(self):
        text = SPEC.read_text(encoding="utf-8")
        self.assertIn("NSLocalNetworkUsageDescription", text)
        self.assertIn("NSBonjourServices", text)
        self.assertIn("_apple-mobdev2._tcp", text)


class WindowTests(_Folder):
    @classmethod
    def setUpClass(cls):
        cls._app = QGuiApplication.instance() or QGuiApplication([])

    def window(self):
        for target, value in (
            ("hearth.device.version_dir", self.root),
            ("hearth.drivers.status", drivers.Report(False, True, "ready")),
            ("hearth.device.scan", []),
        ):
            patcher = patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        controller = Controller()
        controller.pull = lambda: None
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("controller", controller)
        engine.load(QUrl.fromLocalFile(str(QML)))
        self.assertTrue(engine.rootObjects(), "Main.qml did not load")

        def close():
            shiboken6.delete(engine)
            controller.shutdown()

        self.addCleanup(close)
        return controller, engine.rootObjects()[0]

    def settle(self, seconds=0.2):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self._app.processEvents()
            time.sleep(0.01)

    def test_the_selector_shows_only_when_there_is_a_choice(self):
        controller, root = self.window()
        picker = root.findChild(object, "devicePicker")
        one = Candidate("AAA", "Helvio's iPhone", "USB")
        two = Candidate("BBB", "Jaclyn's iPhone", "Wi-Fi", address="x")
        controller._on_scanned(controller._scan_gen, [one], False)
        self.settle()
        self.assertFalse(controller.showDevices)
        controller._on_scanned(controller._scan_gen, [one, two], False)
        self.settle()
        self.assertTrue(controller.showDevices)
        self.assertEqual(picker.property("count"), 2)
        self.assertEqual(picker.property("currentIndex"), 0)

    def test_picking_from_the_list_operates_that_device(self):
        controller, root = self.window()
        picker = root.findChild(object, "devicePicker")
        controller._on_scanned(controller._scan_gen, [Candidate("AAA", "A", "USB"), Candidate("BBB", "B", "Wi-Fi", address="x")], False)
        self.settle()
        picker.activated.emit(1)
        self.settle()
        self.assertEqual(controller._active, "BBB")
        self.assertEqual(picker.property("currentIndex"), 1)

    def test_settings_has_the_wifi_switch_with_its_hint(self):
        controller, root = self.window()
        box = root.findChild(object, "wifiBox")
        self.assertEqual(box.property("text"), "Connect over Wi-Fi")
        self.assertEqual(controller.wifiHint, "Lets Hearth find your paired iPhone on your home network.")
        with patch.object(controller, "_start_scan"):
            controller.setWifiEnabled(False)
        root.openSettings()
        self.assertFalse(box.property("checked"))


if __name__ == "__main__":
    unittest.main()
