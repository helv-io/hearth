import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

import shiboken6
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from hearth import __version__, updates
from hearth.controller import Controller

QML = Path(__file__).resolve().parents[1] / "hearth" / "qml" / "Main.qml"


def _wait(app, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


class _PopupBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        folder = Path(self._folder.name)
        for target, value in (
            ("hearth.updates._path", folder / "updates.json"),
            ("hearth.device.version_dir", folder),
        ):
            patcher = patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def _close(engine, controller):
        shiboken6.delete(engine)
        controller.shutdown()

    def window(self):
        controller = Controller()
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("controller", controller)
        engine.load(QUrl.fromLocalFile(str(QML)))
        self.assertTrue(engine.rootObjects(), "Main.qml did not load")
        self.addCleanup(self._close, engine, controller)
        return controller, engine.rootObjects()[0]


class UpdatePopupTests(_PopupBase):
    def test_no_popup_until_a_newer_version_is_found(self):
        controller, root = self.window()
        notice = root.findChild(object, "updateNotice")
        self.assertIsNotNone(notice)
        self.assertFalse(notice.property("visible"))

    def test_the_popup_shows_the_new_version(self):
        controller, root = self.window()
        controller._on_update_found("0.9.0")
        _wait(self._app, 0.5)
        notice = root.findChild(object, "updateNotice")
        self.assertTrue(notice.property("visible"))
        self.assertEqual(root.findChild(object, "updateTitle").property("text"), "Hearth 0.9.0 is available")
        self.assertEqual(controller.appVersion, __version__)
        for name, label in (("updateDownload", "Open download page"), ("updateLater", "Not now")):
            self.assertEqual(root.findChild(object, name).property("text"), label)
        self.assertEqual(root.findChild(object, "updateSkip").property("text"), "Skip this version")

    def test_not_now_hides_it_and_remembers_nothing(self):
        controller, root = self.window()
        controller._on_update_found("0.9.0")
        controller.dismissUpdate()
        _wait(self._app, 0.5)
        self.assertFalse(root.findChild(object, "updateNotice").property("visible"))
        self.assertEqual(updates.load_state()["skipped"], "")

    def test_skip_remembers_the_version(self):
        controller, root = self.window()
        controller._on_update_found("0.9.0")
        controller.skipUpdate()
        self.assertFalse(controller.updateAvailable)
        self.assertEqual(updates.load_state()["skipped"], "0.9.0")

    def test_the_button_opens_the_latest_release_page(self):
        controller, root = self.window()
        controller._on_update_found("0.9.0")
        with patch.object(QDesktopServices, "openUrl") as opened:
            controller.openUpdatePage()
        self.assertEqual(opened.call_args.args[0].toString(), updates.DOWNLOAD_PAGE)
        self.assertFalse(controller.updateAvailable)

    def test_the_popup_buttons_reach_the_controller(self):
        controller, root = self.window()
        controller._on_update_found("0.9.0")
        _wait(self._app, 0.4)
        notice = root.findChild(object, "updateNotice")
        with patch.object(QDesktopServices, "openUrl") as opened:
            notice.download.emit()
        self.assertTrue(opened.called)
        controller._on_update_found("0.9.0")
        notice.skip.emit()
        self.assertEqual(updates.load_state()["skipped"], "0.9.0")
        controller._on_update_found("0.9.1")
        notice.later.emit()
        self.assertFalse(controller.updateAvailable)

    def test_the_setting_is_on_by_default_and_saved(self):
        controller, root = self.window()
        self.assertTrue(controller.checkUpdates)
        box = root.findChild(object, "updatesBox")
        self.assertEqual(box.property("text"), "Check for updates on startup")
        controller.setCheckUpdates(False)
        self.assertFalse(updates.load_state()["enabled"])
        self.assertFalse(Controller().checkUpdates)
        root.openSettings()
        self.assertFalse(box.property("checked"))
        controller.setCheckUpdates(True)
        root.openSettings()
        self.assertTrue(box.property("checked"))

    def test_turning_it_off_hides_a_showing_popup_and_late_answers_are_dropped(self):
        controller, root = self.window()
        controller._on_update_found("0.9.0")
        controller.setCheckUpdates(False)
        self.assertFalse(controller.updateAvailable)
        controller._on_update_found("0.9.0")
        self.assertFalse(controller.updateAvailable)

    def test_start_does_nothing_when_off(self):
        controller, root = self.window()
        controller.setCheckUpdates(False)
        with patch("hearth.controller._UpdateJob") as job:
            controller.startUpdateCheck()
        job.assert_not_called()

    def test_the_background_check_reaches_the_popup(self):
        controller, root = self.window()
        with patch.object(updates, "fetch_tags", return_value=["v99.0.0", "v0.1.0"]):
            controller.startUpdateCheck()
            controller._update_job.wait(5000)
            _wait(self._app, 0.3)
        self.assertEqual(controller.updateVersion, "99.0.0")

    def test_a_failing_check_leaves_the_window_alone(self):
        controller, root = self.window()
        before = controller.status
        with patch.object(updates, "fetch_tags", side_effect=updates.Unreachable("offline")):
            controller.startUpdateCheck()
            controller._update_job.wait(5000)
            _wait(self._app, 0.3)
        self.assertFalse(controller.updateAvailable)
        self.assertEqual(controller.status, before)


class _FakeGitHub:
    """A local server that answers like the tags list. It counts the requests."""

    def __init__(self, tags=None, status=200):
        self.tags = tags or []
        self.status = status
        self.requests = 0
        self.gate = None
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                outer.requests += 1
                if outer.gate is not None:
                    outer.gate.wait(10)
                body = json.dumps([{"name": name} for name in outer.tags]).encode()
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/tags"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        if self.gate is not None:
            self.gate.set()
        self.server.shutdown()
        self.server.server_close()


class CheckForUpdatesTests(_PopupBase):
    """Every start asks, and the Settings button asks on request. Against a fake server."""

    def github(self, *tags, status=200):
        fake = _FakeGitHub(list(tags), status)
        self.addCleanup(fake.close)
        patcher = patch.object(updates, "TAGS_URL", fake.url)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.object(updates, "__version__", "0.4.0")
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake

    def finish(self, controller, seconds=5):
        end = time.monotonic() + seconds
        while time.monotonic() < end and controller.updateChecking:
            self._app.processEvents()
            time.sleep(0.01)
        _wait(self._app, 0.2)
        self.assertFalse(controller.updateChecking)

    def start_and_wait(self, controller):
        controller.startUpdateCheck()
        controller._update_job.wait(8000)
        _wait(self._app, 0.3)

    def test_every_start_asks_again(self):
        fake = self.github("v0.4.0")
        for expected in (1, 2, 3):
            controller = Controller()
            self.addCleanup(controller.shutdown)
            self.start_and_wait(controller)
            self.assertEqual(fake.requests, expected)

    def test_a_release_made_since_the_last_start_shows_at_once(self):
        fake = self.github("v0.4.0")
        first = Controller()
        self.addCleanup(first.shutdown)
        self.start_and_wait(first)
        self.assertFalse(first.updateAvailable)
        fake.tags = ["v0.4.0", "v0.4.1"]
        second = Controller()
        self.addCleanup(second.shutdown)
        self.start_and_wait(second)
        self.assertEqual(second.updateVersion, "0.4.1")

    def test_the_button_is_in_settings_and_says_what_it_does(self):
        controller, root = self.window()
        button = root.findChild(object, "checkUpdatesNow")
        self.assertEqual(button.property("text"), "Check for updates")
        self.assertTrue(button.property("enabled"))

    def test_up_to_date(self):
        self.github("v0.4.0", "v0.3.0")
        controller, root = self.window()
        controller.checkForUpdatesNow()
        self.finish(controller)
        self.assertEqual(controller.updateResult, "You're up to date.")
        self.assertFalse(controller.updateAvailable)
        self.assertEqual(root.findChild(object, "updateResult").property("text"), "You're up to date.")

    def test_a_newer_version_shows_the_same_popup(self):
        self.github("v0.4.0", "v0.5.0")
        controller, root = self.window()
        controller.checkForUpdatesNow()
        self.finish(controller)
        self.assertEqual(controller.updateVersion, "0.5.0")
        notice = root.findChild(object, "updateNotice")
        self.assertTrue(notice.property("visible"))
        self.assertEqual(root.findChild(object, "updateTitle").property("text"), "Hearth 0.5.0 is available")
        self.assertEqual(root.findChild(object, "updateDownload").property("text"), "Open download page")
        self.assertEqual(controller.updateResult, "Hearth 0.5.0 is available.")

    def test_a_skipped_version_still_shows_when_asked(self):
        self.github("v0.5.0")
        updates.skip("0.5.0")
        controller, root = self.window()
        self.start_and_wait(controller)
        self.assertFalse(controller.updateAvailable, "skipped, so the start stays quiet")
        controller.checkForUpdatesNow()
        self.finish(controller)
        self.assertEqual(controller.updateVersion, "0.5.0")
        self.assertTrue(root.findChild(object, "updateNotice").property("visible"))

    def test_it_asks_even_with_the_startup_check_off(self):
        fake = self.github("v0.5.0")
        controller, root = self.window()
        controller.setCheckUpdates(False)
        controller.checkForUpdatesNow()
        self.finish(controller)
        self.assertEqual(fake.requests, 1)
        self.assertEqual(controller.updateVersion, "0.5.0")

    def test_a_failure_says_so_in_plain_words(self):
        self.github(status=403)
        controller, root = self.window()
        controller.checkForUpdatesNow()
        self.finish(controller)
        self.assertEqual(controller.updateResult, "Couldn't check right now. Try again.")
        self.assertFalse(controller.updateAvailable)

    def test_no_connection_says_the_same(self):
        controller, root = self.window()
        with patch.object(updates, "fetch_tags", side_effect=updates.Unreachable("offline")):
            controller.checkForUpdatesNow()
            self.finish(controller)
        self.assertEqual(controller.updateResult, "Couldn't check right now. Try again.")

    def test_the_button_shows_busy_while_the_rest_of_the_app_stays_free(self):
        fake = self.github("v0.4.0")
        fake.gate = threading.Event()
        controller, root = self.window()
        button = root.findChild(object, "checkUpdatesNow")
        controller.checkForUpdatesNow()
        _wait(self._app, 0.3)
        self.assertTrue(controller.updateChecking)
        self.assertEqual(button.property("text"), "Checking…")
        self.assertFalse(button.property("enabled"))
        self.assertFalse(controller.busy, "no app-wide lock")
        controller.checkForUpdatesNow()  # a second press does nothing
        fake.gate.set()
        self.finish(controller)
        self.assertEqual(fake.requests, 1)
        self.assertEqual(button.property("text"), "Check for updates")
        self.assertTrue(button.property("enabled"))

    def test_the_result_is_cleared_when_settings_open_again(self):
        self.github("v0.4.0")
        controller, root = self.window()
        controller.checkForUpdatesNow()
        self.finish(controller)
        self.assertNotEqual(controller.updateResult, "")
        root.openSettings()
        self.assertEqual(controller.updateResult, "")

    def test_the_answer_is_not_hidden_behind_settings(self):
        controller, root = self.window()
        notice = root.findChild(object, "updateNotice")
        self.assertGreater(notice.property("z"), 20)


if __name__ == "__main__":
    unittest.main()
