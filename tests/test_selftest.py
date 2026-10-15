import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hearth import __main__ as launcher
from hearth import __version__


class SelfTestTests(unittest.TestCase):
    def run_main(self, *args):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.txt"
            with mock.patch.object(sys, "argv", ["hearth", *args, str(report)]):
                code = launcher.main()
            return code, report.read_text(encoding="utf-8")

    def test_version_goes_to_the_file_when_there_is_no_console(self):
        code, text = self.run_main("--version")
        self.assertEqual(code, 0)
        self.assertEqual(text.strip(), f"hearth {__version__}")

    def test_version_does_not_need_stdout(self):
        with mock.patch.object(sys, "stdout", None):
            launcher._say("hello\n")

    def test_selftest_loads_the_window_and_draws_it(self):
        # Its own process, because Qt allows one application object per process.
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.txt"
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
            done = subprocess.run(
                [sys.executable, "-m", "hearth", "--selftest", str(report)],
                env=env, cwd=Path(__file__).resolve().parents[1], timeout=120,
            )
            text = report.read_text(encoding="utf-8")
        code = done.returncode
        self.assertEqual(code, 0, text)
        self.assertIn("device code loaded", text)
        self.assertIn("windows 1", text)
        self.assertTrue(text.strip().endswith("ok"))
