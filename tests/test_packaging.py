import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DMG = "Hearth-macos.dmg"


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


class MacDiskImageTests(unittest.TestCase):
    def settings(self, **defines):
        scope = {"defines": defines}
        exec(compile(read("packaging/macos/dmg-settings.py"), "dmg-settings.py", "exec"), scope)
        return scope

    def test_the_app_and_an_applications_shortcut_are_in_the_image(self):
        got = self.settings(app="dist/Hearth.app")
        self.assertEqual(got["files"], ["dist/Hearth.app"])
        self.assertEqual(got["symlinks"], {"Applications": "/Applications"})

    def test_both_are_placed_side_by_side_in_the_window(self):
        got = self.settings(app="somewhere/Hearth.app")
        left, right = got["icon_locations"]["Hearth.app"], got["icon_locations"]["Applications"]
        self.assertEqual(left[1], right[1], "same row")
        self.assertLess(left[0], right[0], "the app on the left, Applications on the right")
        width, height = got["window_rect"][1]
        self.assertTrue(0 < left[0] < right[0] < width and 0 < left[1] < height)
        self.assertEqual(got["background"], "builtin-arrow")

    def test_the_app_comes_from_the_build_not_the_settings(self):
        got = self.settings()
        self.assertEqual(got["files"], [got["application"]])
        self.assertNotRegex(read("packaging/macos/dmg-settings.py"), r"\d+\.\d+\.\d+")

    def test_the_macos_build_makes_the_dmg_named_hearth_and_checks_it(self):
        text = read(".github/workflows/macos.yml")
        self.assertRegex(text, r"dmgbuild .*-D app=dist/Hearth\.app Hearth " + re.escape(DMG))
        self.assertIn("hdiutil attach", text)
        self.assertIn("--selftest", text)
        self.assertIn("name: " + DMG, text)
        self.assertNotIn(".zip", text)

    def test_the_selftest_runs_on_the_app_inside_the_image(self):
        text = read(".github/workflows/macos.yml")
        self.assertIn("/Volumes/Hearth/Hearth.app/Contents/MacOS/hearth --selftest", text)

    def test_the_release_publishes_the_dmg_and_no_zip(self):
        text = read(".github/workflows/release.yml")
        self.assertEqual(text.count(DMG), 2)
        self.assertNotIn("macos.zip", text)

    def test_the_readme_names_the_dmg(self):
        text = read("README.md")
        self.assertIn(DMG, text)
        self.assertNotIn("macos.zip", text)

    def test_the_bundle_version_comes_from_the_package(self):
        text = read("packaging/pyinstaller/hearth.spec")
        self.assertIn('"CFBundleVersion": __version__', text)
        self.assertIn('"CFBundleShortVersionString": __version__', text)


if __name__ == "__main__":
    unittest.main()
