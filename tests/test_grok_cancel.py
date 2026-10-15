"""Grok sign-in must stop cleanly when the person cancels, closes Settings, or closes the window."""

import tempfile
import threading
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

import shiboken6
from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from hearth import drivers, grok_sso
from hearth.controller import Controller

QML = Path(__file__).resolve().parents[1] / "hearth" / "qml" / "Main.qml"
READY = drivers.Probe(system="Linux", socket_open=True)
FLOW = {
    "device_code": "secret",
    "user_code": "ABCD-1234",
    "verification_uri": "https://auth.example.com/device",
    "verification_uri_complete": "https://auth.example.com/device?code=ABCD-1234",
    "interval": 1,
    "expires_at": time.time() + 600,
}
PATIENCE = 5.0


def wait_for(test, condition, what):
    end = time.time() + PATIENCE
    while time.time() < end:
        QCoreApplication.processEvents()
        if condition():
            return
        time.sleep(0.01)
    test.fail(f"timed out waiting for {what}")


class PollTests(unittest.TestCase):
    def setUp(self):
        self._home = tempfile.TemporaryDirectory()
        patcher = patch.object(grok_sso, "config_dir", return_value=Path(self._home.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._home.cleanup)
        endpoints = patch.object(grok_sso, "endpoints", return_value={"token": "https://auth.example.com/token"})
        endpoints.start()
        self.addCleanup(endpoints.stop)

    def flow(self, interval=30):
        return {**FLOW, "interval": interval, "expires_at": time.time() + 600}

    def test_cancel_ends_the_wait_at_once(self):
        cancel = Event()
        threading.Timer(0.1, cancel.set).start()
        started = time.time()
        with patch.object(grok_sso, "_post_form") as asked:
            result = grok_sso.poll(self.flow(), cancel)
        self.assertEqual(result, "cancelled")
        self.assertLess(time.time() - started, 2)
        asked.assert_not_called()

    def test_a_cancel_during_a_request_saves_nothing(self):
        cancel = Event()

        def reply(url, form, timeout=0):
            cancel.set()
            return 200, {"access_token": "a", "refresh_token": "r", "expires_in": 3600}

        # The request is out when the cancel lands, so its answer must be thrown away.
        with patch.object(grok_sso, "_post_form", side_effect=reply):
            result = grok_sso.poll(self.flow(interval=1), cancel)
        self.assertEqual(result, "cancelled")
        self.assertFalse(grok_sso.signed_in())

    def test_saying_no_in_the_browser_is_a_cancel_not_an_error(self):
        with patch.object(grok_sso, "_post_form", return_value=(400, {"error": "access_denied"})):
            result = grok_sso.poll(self.flow(interval=1), Event())
        self.assertEqual(result, "cancelled")
        self.assertFalse(grok_sso.signed_in())

    def test_a_real_failure_still_says_why(self):
        with patch.object(grok_sso, "_post_form", return_value=(403, {})):
            with self.assertRaises(RuntimeError) as caught:
                grok_sso.poll(self.flow(interval=1), Event())
        self.assertIn("cannot use sign-in", str(caught.exception))

    def test_an_expired_code_says_to_start_again(self):
        flow = {**self.flow(interval=1), "expires_at": time.time() - 1}
        with self.assertRaises(RuntimeError) as caught:
            grok_sso.poll(flow, Event())
        self.assertIn("Start again", str(caught.exception))

    def test_sign_in_requests_are_short(self):
        seen = []

        def reply(url, form, timeout=None):
            seen.append(timeout)
            return 200, {"access_token": "a", "refresh_token": "r", "expires_in": 3600}

        with patch.object(grok_sso, "_post_form", side_effect=reply):
            self.assertEqual(grok_sso.poll(self.flow(interval=1), Event()), "ok")
        self.assertEqual(seen, [grok_sso.SIGN_IN_TIMEOUT])
        self.assertTrue(grok_sso.signed_in())


class SignInControllerTests(unittest.TestCase):
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
        self._home = tempfile.TemporaryDirectory()
        config = patch.object(grok_sso, "config_dir", return_value=Path(self._home.name))
        config.start()
        self.addCleanup(config.stop)
        browser = patch("hearth.controller.QDesktopServices.openUrl")
        self.opened = browser.start()
        self.addCleanup(browser.stop)
        self.addCleanup(self._home.cleanup)
        with patch.object(drivers, "live_probe", return_value=READY):
            self.controller = Controller()
        self.addCleanup(self.controller.shutdown)

    def fake_sign_in(self, outcomes):
        """Patch the network side. Each call to poll takes the next outcome and honors the cancel flag."""
        queue = list(outcomes)
        self.polled = []

        def poll(flow, cancel):
            what = queue.pop(0)
            self.polled.append(what)
            if what == "wait":
                cancel.wait(PATIENCE)
                return "cancelled"
            if what == "ok":
                return "ok"
            if what == "late-error":
                cancel.wait(PATIENCE)
                raise RuntimeError("Could not reach Grok sign-in. timed out")
            raise RuntimeError(what)

        for target in (
            patch.object(grok_sso, "start_device", side_effect=lambda: dict(FLOW)),
            patch.object(grok_sso, "poll", side_effect=poll),
        ):
            target.start()
            self.addCleanup(target.stop)

    def waiting_with_code(self):
        return self.controller.grokWaiting and self.controller.grokCode != ""

    def test_cancel_gives_the_app_back_at_once(self):
        self.fake_sign_in(["wait"])
        self.controller.startGrokSignIn()
        wait_for(self, self.waiting_with_code, "the code")
        self.assertTrue(self.controller.busy)
        self.controller.cancelGrokSignIn()
        self.assertFalse(self.controller.busy)
        self.assertFalse(self.controller.grokWaiting)
        self.assertEqual(self.controller.grokCode, "")
        self.assertFalse(self.controller.grokSignedIn)
        self.assertEqual(self.controller._status, "Grok sign-in cancelled.")
        self.assertFalse(self.controller._error)

    def test_other_steps_work_after_a_cancel(self):
        self.fake_sign_in(["wait"])
        self.controller.startGrokSignIn()
        wait_for(self, self.waiting_with_code, "the code")
        self.controller.cancelGrokSignIn()
        with patch("hearth.controller._Job.start") as started:
            self.controller.refreshModels()
        started.assert_called_once()
        self.assertNotEqual(self.controller._status, "Wait for the current step to finish.")

    def test_nothing_is_shown_when_the_stopped_worker_finishes(self):
        self.fake_sign_in(["late-error"])
        self.controller.startGrokSignIn()
        wait_for(self, self.waiting_with_code, "the code")
        job = self.controller._job
        self.controller.cancelGrokSignIn()
        wait_for(self, lambda: not job.isRunning(), "the worker to stop")
        for _ in range(20):
            QCoreApplication.processEvents()
            time.sleep(0.01)
        self.assertEqual(self.controller._status, "Grok sign-in cancelled.")
        self.assertFalse(self.controller._error)
        self.assertEqual(self.controller._retired, [])

    def test_cancel_then_try_again_signs_in(self):
        self.fake_sign_in(["late-error", "ok"])
        self.controller.startGrokSignIn()
        wait_for(self, self.waiting_with_code, "the first code")
        first = self.controller._job
        self.controller.cancelGrokSignIn()
        self.controller.startGrokSignIn()
        self.assertTrue(self.controller.grokWaiting)
        self.assertIsNot(self.controller._job, first)
        wait_for(self, lambda: self.controller._status == "Signed in to Grok.", "the second sign-in")
        wait_for(self, lambda: not self.controller.busy, "the app to be free")
        self.assertFalse(self.controller.grokWaiting)
        self.assertFalse(self.controller._error)
        # The first worker stopping late did not disturb the second sign-in.
        wait_for(self, lambda: not first.isRunning(), "the first worker to stop")
        QCoreApplication.processEvents()
        self.assertEqual(self.controller._status, "Signed in to Grok.")

    def test_cancel_before_the_code_arrives_opens_no_browser(self):
        gate = Event()

        def slow_start():
            gate.wait(PATIENCE)
            return dict(FLOW)

        with patch.object(grok_sso, "start_device", side_effect=slow_start), \
                patch.object(grok_sso, "poll", side_effect=AssertionError("must not poll")):
            self.controller.startGrokSignIn()
            self.assertTrue(self.controller.grokWaiting)
            job = self.controller._job
            self.controller.cancelGrokSignIn()
            self.assertFalse(self.controller.busy)
            gate.set()
            wait_for(self, lambda: not job.isRunning(), "the worker to stop")
            QCoreApplication.processEvents()
        self.opened.assert_not_called()
        self.assertEqual(self.controller.grokCode, "")
        self.assertFalse(self.controller._error)

    def test_a_real_error_shows_a_plain_message_and_frees_the_app(self):
        self.fake_sign_in(["The sign-in code expired. Start again."])
        self.controller.startGrokSignIn()
        wait_for(self, lambda: self.controller._error, "the error")
        wait_for(self, lambda: not self.controller.busy, "the app to be free")
        self.assertEqual(self.controller._status, "The sign-in code expired. Start again.")
        self.assertFalse(self.controller.grokWaiting)
        self.assertEqual(self.controller.grokCode, "")

    def test_cancel_does_nothing_when_no_sign_in_is_running(self):
        self.controller.cancelGrokSignIn()
        self.assertFalse(self.controller.busy)
        self.assertEqual(self.controller._status, "Plug in an iPhone or iPad.")

    def test_closing_the_window_mid_sign_in_stops_the_worker(self):
        self.fake_sign_in(["wait"])
        self.controller.startGrokSignIn()
        wait_for(self, self.waiting_with_code, "the code")
        job = self.controller._job
        started = time.time()
        self.controller.shutdown()
        self.assertFalse(job.isRunning())
        self.assertLess(time.time() - started, 3)

    def test_closing_the_window_after_a_cancel_stops_the_old_worker_too(self):
        self.fake_sign_in(["late-error", "wait"])
        self.controller.startGrokSignIn()
        wait_for(self, self.waiting_with_code, "the first code")
        first = self.controller._job
        self.controller.cancelGrokSignIn()
        self.controller.startGrokSignIn()
        wait_for(self, self.waiting_with_code, "the second code")
        second = self.controller._job
        self.controller.shutdown()
        self.assertFalse(first.isRunning())
        self.assertFalse(second.isRunning())

    def test_closing_settings_cancels_a_waiting_sign_in(self):
        self.fake_sign_in(["wait"])
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("controller", self.controller)
        engine.load(QUrl.fromLocalFile(str(QML)))
        try:
            window = engine.rootObjects()[0]
            window.setProperty("settingsOpen", True)
            self.controller.startGrokSignIn()
            wait_for(self, self.waiting_with_code, "the code")
            window.setProperty("settingsOpen", False)
            self.assertFalse(self.controller.grokWaiting)
            self.assertFalse(self.controller.busy)
        finally:
            shiboken6.delete(engine)

    def test_the_button_turns_into_cancel_while_waiting(self):
        self.fake_sign_in(["wait"])
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("controller", self.controller)
        engine.load(QUrl.fromLocalFile(str(QML)))
        try:
            window = engine.rootObjects()[0]
            window.setProperty("providerIsGrok", True)
            window.setProperty("settingsOpen", True)
            button = window.findChild(object, "grokButton")
            self.assertEqual(button.property("text"), "Sign in with Grok")
            self.controller.startGrokSignIn()
            wait_for(self, self.waiting_with_code, "the code")
            self.assertEqual(button.property("text"), "Cancel sign-in")
            self.assertTrue(button.property("enabled"))
        finally:
            shiboken6.delete(engine)


if __name__ == "__main__":
    unittest.main()
