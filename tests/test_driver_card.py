import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import shiboken6
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from hearth import drivers
from hearth.controller import Controller

QML = Path(__file__).resolve().parents[1] / "hearth" / "qml" / "Main.qml"
NEEDS = drivers.Probe(system="Linux", have_systemctl=True, package_manager="pacman")
READY = drivers.Probe(system="Linux", socket_open=True)


class DriverCardTests(unittest.TestCase):
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

    @staticmethod
    def _close(engine, controller):
        # The window goes first. Otherwise its bindings read a controller that is already gone.
        shiboken6.delete(engine)
        controller.shutdown()

    def controller(self):
        with patch.object(drivers, "live_probe", return_value=NEEDS):
            return Controller()

    def test_the_command_is_hidden_until_the_button_fails(self):
        controller = self.controller()
        self.assertTrue(controller.driverNeeded)
        self.assertEqual(controller.driverManual, "")
        with patch.object(drivers, "live_probe", return_value=NEEDS):
            controller._on_driver("The setup did not finish. Try again.")
        self.assertIn("pacman -S", controller.driverManual)

    def test_the_command_is_gone_after_success(self):
        controller = self.controller()
        with patch.object(drivers, "live_probe", return_value=NEEDS):
            controller._on_driver("The setup did not finish. Try again.")
        with patch.object(drivers, "live_probe", return_value=READY):
            controller._on_driver("USB support is ready.")
        self.assertEqual(controller.driverManual, "")
        self.assertFalse(controller.driverNeeded)

    def test_a_job_failure_also_opens_the_fallback(self):
        controller = self.controller()

        class Job:
            kind = "driver"

        controller._job = Job()
        with patch.object(drivers, "live_probe", return_value=NEEDS):
            controller._on_failed("Hearth could not run the setup on this computer. Try again.")
        self.assertNotEqual(controller.driverManual, "")

    def test_copy_puts_the_command_on_the_clipboard(self):
        controller = self.controller()
        with patch.object(drivers, "live_probe", return_value=NEEDS):
            controller._on_driver("The setup did not finish. Try again.")
        controller.copyDriverManual()
        self.assertEqual(QGuiApplication.clipboard().text(), controller.driverManual)

    def test_the_window_loads_and_folds_the_steps_away(self):
        controller = self.controller()
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("controller", controller)
        engine.load(QUrl.fromLocalFile(str(QML)))
        self.assertTrue(engine.rootObjects())
        root = engine.rootObjects()[0]
        card = root.findChild(object, "driverCard")
        self.assertIsNotNone(card)
        self.assertTrue(card.property("visible"))
        toggle = root.findChild(object, "manualToggle")
        steps = root.findChild(object, "manualSteps")
        self.assertFalse(toggle.property("visible"))
        with patch.object(drivers, "live_probe", return_value=NEEDS):
            controller._on_driver("The setup did not finish. Try again.")
        self.assertTrue(toggle.property("visible"))
        self.assertFalse(steps.property("visible"))
        card.setProperty("manualOpen", True)
        self.assertTrue(steps.property("visible"))
        self.addCleanup(self._close, engine, controller)


if __name__ == "__main__":
    unittest.main()
