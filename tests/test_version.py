import re
import tomllib
import unittest
from pathlib import Path

from hearth import __version__

ROOT = Path(__file__).resolve().parents[1]


class VersionTests(unittest.TestCase):
    def test_package_and_project_agree(self):
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(data["project"]["version"], __version__)

    def test_newest_metainfo_release_is_this_version(self):
        text = (ROOT / "packaging/linux/io.helv.Hearth.metainfo.xml").read_text(encoding="utf-8")
        first = re.search(r'<release version="([^"]+)"', text)
        self.assertIsNotNone(first)
        self.assertEqual(first.group(1), __version__)

    def test_changelog_has_a_section_for_this_version(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        first = re.search(r"^## (\S+)", text, re.MULTILINE)
        self.assertIsNotNone(first)
        self.assertEqual(first.group(1), __version__)

    def test_the_build_spec_does_not_hardcode_a_version(self):
        text = (ROOT / "packaging/pyinstaller/hearth.spec").read_text(encoding="utf-8")
        self.assertNotRegex(text, r'"\d+\.\d+\.\d+"')
