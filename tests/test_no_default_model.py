"""Hearth has no built-in model. The person picks one from their provider's list, and Organize says what is missing."""

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import shiboken6
from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from hearth import ai, drivers, grok_sso, settings
from hearth.controller import Controller

QML = Path(__file__).resolve().parents[1] / "hearth" / "qml" / "Main.qml"
READY = drivers.Probe(system="Linux", socket_open=True)
OPENAI = "https://api.openai.com/v1"
STATE = [[], [[{"id": "com.example.a", "name": "A"}]]]


def wait_for(test, condition, what):
    end = time.time() + 5
    while time.time() < end:
        QCoreApplication.processEvents()
        if condition():
            return
        time.sleep(0.01)
    test.fail(f"timed out waiting for {what}")


class Home(unittest.TestCase):
    """A private config and cache folder, so a test never reads the real settings."""

    def setUp(self):
        self._home = tempfile.TemporaryDirectory()
        self.addCleanup(self._home.cleanup)
        self.home = Path(self._home.name)
        for module in (settings, grok_sso):
            patcher = patch.object(module, "config_dir", return_value=self.home)
            patcher.start()
            self.addCleanup(patcher.stop)
        cache = patch.object(settings, "cache_dir", return_value=self.home)
        cache.start()
        self.addCleanup(cache.stop)
        env = patch.dict("os.environ", {"XAI_API_KEY": ""})
        env.start()
        self.addCleanup(env.stop)

    def write_settings(self, **values):
        (self.home / "settings.json").write_text(json.dumps(values), encoding="utf-8")


class SettingsTests(Home):
    def test_a_first_run_has_no_model(self):
        self.assertEqual(settings.load()["model"], "")

    def test_saving_without_a_model_keeps_it_empty(self):
        self.assertEqual(settings.save(OPENAI, "", None, provider="openai")["model"], "")
        self.assertEqual(settings.load()["model"], "")

    def test_a_model_saved_by_an_older_version_stays_the_persons_pick(self):
        self.write_settings(provider="grok", base_url="https://api.x.ai/v1", model="grok-4.7")
        self.assertEqual(settings.load()["model"], "grok-4.7")

    def test_a_pick_is_remembered(self):
        settings.save(OPENAI, "picked-one", None, provider="openai")
        self.assertEqual(settings.load()["model"], "picked-one")

    def test_the_last_list_is_kept_per_endpoint(self):
        settings.remember_models(OPENAI, ["b", "a", "a"])
        self.assertEqual(settings.last_models(OPENAI + "/"), ["a", "b"])
        self.assertEqual(settings.last_models("https://api.x.ai/v1"), [])

    def test_an_empty_list_never_replaces_a_good_one(self):
        settings.remember_models(OPENAI, ["a"])
        settings.remember_models(OPENAI, [])
        self.assertEqual(settings.last_models(OPENAI), ["a"])

    def test_a_damaged_list_file_is_just_no_list(self):
        (self.home / "models.json").write_text("{nope", encoding="utf-8")
        self.assertEqual(settings.last_models(OPENAI), [])


class ControllerTests(Home):
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

    def make(self):
        with patch.object(drivers, "live_probe", return_value=READY):
            controller = Controller()
        controller._state = STATE
        self.addCleanup(controller.shutdown)
        return controller

    def organize_is_refused_without_calling_the_provider(self, controller):
        with patch.object(ai, "organize", side_effect=AssertionError("must not call the provider")):
            controller.propose("sort by name")
        self.assertFalse(controller.busy)
        self.assertTrue(controller._error)
        return controller._status

    def test_with_no_key_and_no_list_it_says_to_connect(self):
        controller = self.make()
        self.assertEqual(controller.model, "")
        self.assertEqual(controller.modelNeed, "connect")
        self.assertEqual(self.organize_is_refused_without_calling_the_provider(controller),
                         "Connect a provider to pick a model.")

    def test_the_message_has_no_provider_error_in_it(self):
        text = self.organize_is_refused_without_calling_the_provider(self.make())
        for word in ("401", "403", "HTTP", "endpoint", "API key"):
            self.assertNotIn(word, text)

    def test_with_a_list_it_asks_for_a_pick(self):
        settings.save(OPENAI, "", "sk-test", provider="openai")
        settings.remember_models(OPENAI, ["a", "b"])
        controller = self.make()
        self.assertEqual(controller.modelNeed, "pick")
        self.assertEqual(list(controller.modelChoices), ["a", "b"])
        self.assertEqual(self.organize_is_refused_without_calling_the_provider(controller), "Pick a model first.")

    def test_a_key_but_no_list_says_the_list_cannot_be_reached(self):
        settings.save(OPENAI, "", "sk-test", provider="openai")
        controller = self.make()
        with patch.object(ai, "list_models", side_effect=OSError("offline")):
            text = self.organize_is_refused_without_calling_the_provider(controller)
            wait_for(self, lambda: not controller._list_job.isRunning(), "the list request")
        self.assertIn("model list", text)
        self.assertNotIn("offline", text)

    def test_the_picked_model_is_remembered_and_organize_uses_it(self):
        settings.save(OPENAI, "", "sk-test", provider="openai")
        settings.remember_models(OPENAI, ["a", "b"])
        controller = self.make()
        controller.chooseModel("b")
        self.assertEqual(controller.modelNeed, "")
        self.assertEqual(settings.load()["model"], "b")
        self.assertEqual(settings.load()["provider"], "openai")
        self.assertEqual(settings.load()["key"], "sk-test")
        seen = []

        def organize(base, key, model, *args, **kwargs):
            seen.append(model)
            return {"summary": "ok", "pages": []}

        with patch.object(ai, "organize", side_effect=organize):
            controller.propose("sort by name")
            wait_for(self, lambda: seen and not controller.busy, "organize")
        self.assertEqual(seen, ["b"])

    def test_an_old_saved_model_still_works_without_a_list(self):
        self.write_settings(provider="grok", base_url="https://api.x.ai/v1", model="grok-4.7")
        controller = self.make()
        self.assertEqual(controller.model, "grok-4.7")
        self.assertEqual(controller.modelNeed, "")

    def test_offline_the_last_list_is_still_offered(self):
        settings.save(OPENAI, "", "sk-test", provider="openai")
        settings.remember_models(OPENAI, ["a"])
        controller = self.make()
        with patch.object(ai, "list_models", side_effect=OSError("offline")):
            controller.refreshModelsQuietly()
            wait_for(self, lambda: not controller._list_job.isRunning(), "the list request")
            QCoreApplication.processEvents()
        self.assertEqual(list(controller.modelChoices), ["a"])
        self.assertFalse(controller._error)
        self.assertEqual(controller.status, "Plug in an iPhone or iPad.")

    def test_a_fresh_list_replaces_the_old_one_and_is_kept(self):
        settings.save(OPENAI, "", "sk-test", provider="openai")
        settings.remember_models(OPENAI, ["old"])
        controller = self.make()
        with patch.object(ai, "list_models", return_value=["new1", "new2"]):
            controller.refreshModelsQuietly()
            wait_for(self, lambda: list(controller.modelChoices) == ["new1", "new2"], "the new list")
        self.assertEqual(settings.last_models(OPENAI), ["new1", "new2"])

    def test_a_list_for_another_provider_is_not_shown(self):
        settings.save(OPENAI, "", "sk-test", provider="openai")
        controller = self.make()
        controller._on_models_quietly("https://api.mistral.ai/v1", ["other"])
        self.assertEqual(list(controller.modelChoices), [])
        self.assertEqual(settings.last_models("https://api.mistral.ai/v1"), ["other"])

    def test_the_picker_shows_when_a_pick_is_needed_and_connect_when_it_is_not_possible(self):
        controller = self.make()
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("controller", controller)
        engine.load(QUrl.fromLocalFile(str(QML)))
        try:
            window = engine.rootObjects()[0]
            picker = window.findChild(object, "modelPicker")
            connect = window.findChild(object, "connectButton")
            self.assertFalse(picker.property("visible"))
            self.assertTrue(connect.property("visible"))
            self.assertEqual(connect.property("text"), "Connect a provider")
            controller._on_models_quietly(settings.load()["base_url"], ["a", "b"])
            QCoreApplication.processEvents()
            self.assertTrue(picker.property("visible"))
            self.assertFalse(connect.property("visible"))
            self.assertEqual(picker.property("displayText"), "Pick a model")
            controller.chooseModel("a")
            QCoreApplication.processEvents()
            self.assertFalse(picker.property("visible"))
            self.assertFalse(connect.property("visible"))
        finally:
            shiboken6.delete(engine)


if __name__ == "__main__":
    unittest.main()
