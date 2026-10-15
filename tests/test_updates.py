import json
import os
import ssl
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from hearth import updates

ROOT = Path(__file__).resolve().parents[1]


class Folder(unittest.TestCase):
    """Keep the saved choices in a temporary folder, never the real one."""

    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        patcher = mock.patch.object(updates, "_path", return_value=Path(self._folder.name) / "updates.json")
        patcher.start()
        self.addCleanup(patcher.stop)


class VersionTests(unittest.TestCase):
    def test_numbers_compare_as_numbers_not_as_text(self):
        self.assertTrue(updates.is_newer("0.10.0", "0.9.0"))
        self.assertTrue(updates.is_newer("v1.0.0", "0.99.99"))
        self.assertFalse(updates.is_newer("0.9.0", "0.10.0"))

    def test_the_same_version_is_not_newer(self):
        self.assertFalse(updates.is_newer("0.5.0", "0.5.0"))
        self.assertFalse(updates.is_newer("v0.5.0", "0.5.0"))

    def test_a_release_is_newer_than_its_own_pre_release(self):
        self.assertTrue(updates.is_newer("0.5.0", "0.5.0rc1"))
        self.assertTrue(updates.is_newer("0.5.0", "0.5.0-rc.2"))
        self.assertFalse(updates.is_newer("0.5.0-rc1", "0.5.0"))
        self.assertTrue(updates.is_newer("0.5.0-rc10", "0.5.0-rc9"))

    def test_odd_text_is_never_newer(self):
        for odd in ("", "latest", "v1", "v1.2", "nightly", "vfoo", "1.2.3.4", "v0.5.0-", None):
            self.assertFalse(updates.is_newer(odd, "0.4.0"), odd)
            self.assertFalse(updates.is_newer("0.5.0", odd), odd)

    def test_build_metadata_is_ignored(self):
        self.assertFalse(updates.is_newer("v0.5.0+abc", "0.5.0"))

    def test_newest_release_picks_the_highest_full_release(self):
        tags = ["v0.9.0", "v0.10.0", "v0.11.0-rc1", "nightly", "0.99.0", "v0.4.0", "v1", "vNext"]
        self.assertEqual(str(updates.newest_release(tags)), "0.10.0")

    def test_newest_release_of_nothing_useful_is_none(self):
        self.assertIsNone(updates.newest_release([]))
        self.assertIsNone(updates.newest_release(["nightly", "v0.1.0-beta"]))

    def test_a_dev_or_unversioned_build_is_recognised(self):
        for build in ("", "dev", "0.0.0", "0.5.0.dev1", "0.5.0-dev", "unknown"):
            self.assertTrue(updates.is_dev_build(build), build)
        for build in ("0.4.0", "1.0.0", "0.5.0rc1"):
            self.assertFalse(updates.is_dev_build(build), build)

    def test_the_project_name_is_one_constant_and_matches_the_package(self):
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(data["project"]["urls"]["Homepage"], f"https://github.com/{updates.REPO}")
        self.assertIn(updates.REPO, updates.TAGS_URL)
        self.assertEqual(updates.DOWNLOAD_PAGE, f"https://github.com/{updates.REPO}/releases/latest")
        elsewhere = [
            str(f.relative_to(ROOT))
            for f in (ROOT / "hearth").rglob("*")
            if f.suffix in (".py", ".qml") and f.name != "updates.py" and "helv-io/hearth" in f.read_text(encoding="utf-8")
        ]
        self.assertEqual(elsewhere, [], "the project name lives in updates.REPO only")


class OfferTests(Folder):
    """The check at start."""

    def fetch(self, *tags):
        return mock.Mock(return_value=list(tags))

    def test_a_newer_tag_is_offered(self):
        fetch = self.fetch("v0.4.0", "v0.5.0")
        self.assertEqual(updates.offer("0.4.0", fetch), "0.5.0")

    def test_nothing_newer_means_no_popup(self):
        self.assertEqual(updates.offer("0.5.0", self.fetch("v0.5.0", "v0.4.0")), "")
        self.assertEqual(updates.offer("0.6.0", self.fetch("v0.5.0")), "")

    def test_a_pre_release_tag_is_not_offered(self):
        self.assertEqual(updates.offer("0.4.0", self.fetch("v0.4.0", "v0.5.0-rc1")), "")

    def test_every_start_asks(self):
        fetch = self.fetch("v0.5.0")
        for _ in range(3):
            self.assertEqual(updates.offer("0.4.0", fetch), "0.5.0")
        self.assertEqual(fetch.call_count, 3)

    def test_a_new_release_shows_at_the_very_next_start(self):
        self.assertEqual(updates.offer("0.4.0", self.fetch("v0.4.0")), "")
        self.assertEqual(updates.offer("0.4.0", self.fetch("v0.4.0", "v0.4.1")), "0.4.1")

    def test_there_is_no_once_a_day_limit_left(self):
        self.assertFalse(hasattr(updates, "CHECK_EVERY_SECONDS"))
        self.assertFalse(hasattr(updates, "due"))
        self.assertNotIn("last_check", updates.load_state())

    def test_a_skipped_version_stays_quiet(self):
        updates.skip("0.5.0")
        self.assertEqual(updates.offer("0.4.0", self.fetch("v0.5.0")), "")

    def test_a_version_after_the_skipped_one_is_offered(self):
        updates.skip("0.5.0")
        self.assertEqual(updates.offer("0.4.0", self.fetch("v0.5.1")), "0.5.1")

    def test_the_skip_is_remembered_across_runs(self):
        updates.skip("0.5.0")
        self.assertEqual(updates.load_state()["skipped"], "0.5.0")

    def test_turned_off_means_no_request_and_no_popup(self):
        updates.set_enabled(False)
        fetch = self.fetch("v0.5.0")
        self.assertEqual(updates.offer("0.4.0", fetch), "")
        fetch.assert_not_called()

    def test_a_dev_build_makes_no_request(self):
        fetch = self.fetch("v9.9.9")
        for build in ("", "0.0.0", "0.5.0.dev1"):
            self.assertEqual(updates.offer(build, fetch), "")
        fetch.assert_not_called()

    def test_failures_are_silent(self):
        failures = [
            updates.Unreachable("offline"),
            ValueError("GitHub answered 403"),
            RuntimeError("anything"),
            KeyError("x"),
        ]
        for failure in failures:
            with self.subTest(failure=failure):
                self.assertEqual(updates.offer("0.4.0", mock.Mock(side_effect=failure)), "")

    def test_a_useless_answer_is_silent(self):
        self.assertEqual(updates.offer("0.4.0", self.fetch()), "")
        self.assertEqual(updates.offer("0.4.0", self.fetch("nightly")), "")

    def test_a_failure_is_asked_again_at_the_next_start(self):
        updates.offer("0.4.0", mock.Mock(side_effect=ValueError("GitHub answered 403")))
        fetch = self.fetch("v0.5.0")
        self.assertEqual(updates.offer("0.4.0", fetch), "0.5.0")
        fetch.assert_called_once()

    def test_a_failure_keeps_the_last_good_answer(self):
        updates.offer("0.4.0", self.fetch("v0.5.0"))
        later = updates.offer("0.4.0", mock.Mock(side_effect=ValueError("403")))
        self.assertEqual(later, "0.5.0")

    def test_a_damaged_state_file_is_ignored(self):
        updates._path().write_text("{not json", encoding="utf-8")
        self.assertEqual(updates.offer("0.4.0", self.fetch("v0.5.0")), "0.5.0")
        updates._path().write_text(json.dumps({"enabled": "no", "skipped": 3}), encoding="utf-8")
        self.assertTrue(updates.load_state()["enabled"])

    def test_an_unwritable_folder_is_silent(self):
        with mock.patch.object(Path, "write_text", side_effect=OSError("read only")):
            self.assertEqual(updates.offer("0.4.0", self.fetch("v0.5.0")), "0.5.0")


class CheckNowTests(Folder):
    """The Check for updates button."""

    def fetch(self, *tags):
        return mock.Mock(return_value=list(tags))

    def test_newer_gives_the_version(self):
        self.assertEqual(updates.check_now("0.4.0", self.fetch("v0.4.0", "v0.5.0")), (updates.NEWER, "0.5.0"))

    def test_the_same_version_is_up_to_date(self):
        self.assertEqual(updates.check_now("0.5.0", self.fetch("v0.5.0", "v0.4.0")), (updates.CURRENT, ""))

    def test_a_newer_version_that_was_skipped_is_still_reported(self):
        updates.skip("0.5.0")
        self.assertEqual(updates.check_now("0.4.0", self.fetch("v0.5.0")), (updates.NEWER, "0.5.0"))

    def test_it_asks_even_when_the_startup_check_is_off(self):
        updates.set_enabled(False)
        fetch = self.fetch("v0.5.0")
        self.assertEqual(updates.check_now("0.4.0", fetch), (updates.NEWER, "0.5.0"))
        fetch.assert_called_once()

    def test_every_kind_of_failure_is_failed(self):
        for failure in (updates.Unreachable("offline"), ValueError("GitHub answered 403"), RuntimeError("x")):
            with self.subTest(failure=failure):
                self.assertEqual(updates.check_now("0.4.0", mock.Mock(side_effect=failure)), (updates.FAILED, ""))

    def test_an_answer_with_no_release_is_failed_not_up_to_date(self):
        self.assertEqual(updates.check_now("0.4.0", self.fetch()), (updates.FAILED, ""))
        self.assertEqual(updates.check_now("0.4.0", self.fetch("nightly", "v0.5.0-rc1")), (updates.FAILED, ""))


class FetchTests(unittest.TestCase):
    def reply(self, body):
        handle = mock.MagicMock()
        handle.__enter__.return_value.read.return_value = body if isinstance(body, bytes) else json.dumps(body).encode()
        return handle

    def test_it_reads_tag_names_from_the_api(self):
        rows = [{"name": "v0.5.0", "commit": {}}, {"name": "v0.4.0"}, {"nope": 1}, "x"]
        with mock.patch("urllib.request.urlopen", return_value=self.reply(rows)) as opened:
            self.assertEqual(updates.fetch_tags(), ["v0.5.0", "v0.4.0"])
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, updates.TAGS_URL)
        self.assertEqual(opened.call_args.kwargs["timeout"], updates.TIMEOUT_SECONDS)
        self.assertIsNone(request.get_header("Authorization"), "the request is unauthenticated")
        self.assertLessEqual(updates.TIMEOUT_SECONDS, 10)

    def test_it_checks_certificates(self):
        with mock.patch("urllib.request.urlopen", return_value=self.reply([])) as opened:
            updates.fetch_tags()
        context = opened.call_args.kwargs["context"]
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_an_http_error_is_a_plain_failure(self):
        error = urllib.error.HTTPError(updates.TAGS_URL, 403, "rate limited", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(ValueError):
                updates.fetch_tags()

    def test_no_connection_is_unreachable(self):
        for failure in (urllib.error.URLError("no network"), TimeoutError(), OSError("down")):
            with mock.patch("urllib.request.urlopen", side_effect=failure):
                with self.assertRaises(updates.Unreachable):
                    updates.fetch_tags()

    def test_a_wrong_shape_is_a_plain_failure(self):
        with mock.patch("urllib.request.urlopen", return_value=self.reply({"message": "x"})):
            with self.assertRaises(ValueError):
                updates.fetch_tags()
        with mock.patch("urllib.request.urlopen", return_value=self.reply(b"<html>")):
            with self.assertRaises(ValueError):
                updates.fetch_tags()


class SelfTestIsOffline(unittest.TestCase):
    def test_the_selftest_makes_no_network_call(self):
        code = (
            "import sys, socket, urllib.request\n"
            "calls = []\n"
            "def spy(*a, **k):\n"
            "    calls.append(a)\n"
            "    raise OSError('no network in the selftest')\n"
            "urllib.request.urlopen = spy\n"
            "socket.getaddrinfo = spy\n"
            "from hearth import __main__ as m\n"
            "status = m._selftest(sys.argv[1])\n"
            "print('CALLS', len(calls), 'STATUS', status)\n"
        )
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.txt"
            done = subprocess.run(
                [sys.executable, "-c", code, str(report)],
                env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
                cwd=ROOT, capture_output=True, text=True, timeout=120,
            )
        self.assertIn("CALLS 0 STATUS 0", done.stdout, done.stdout + done.stderr)

    def test_a_new_controller_makes_no_request_until_asked(self):
        from hearth.controller import Controller
        with tempfile.TemporaryDirectory() as folder, \
                mock.patch.object(updates, "_path", return_value=Path(folder) / "updates.json"), \
                mock.patch("hearth.device.version_dir", return_value=Path(folder)), \
                mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")):
            controller = Controller()
            self.assertFalse(controller.updateAvailable)
            controller.shutdown()


if __name__ == "__main__":
    unittest.main()
