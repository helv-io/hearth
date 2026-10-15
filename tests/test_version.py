import tomllib
import unittest
from pathlib import Path

from hearth import __version__


class VersionTests(unittest.TestCase):
    def test_package_and_project_agree(self):
        project = Path(__file__).resolve().parents[1] / "pyproject.toml"
        data = tomllib.loads(project.read_text(encoding="utf-8"))
        self.assertEqual(data["project"]["version"], __version__)
        self.assertEqual(__version__, "0.2.0")
