import tempfile
import time
import unittest
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


class UpdatePopupTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
