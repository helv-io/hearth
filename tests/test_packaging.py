import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DMG = "Hearth-macos.dmg"
INTEL_DMG = "Hearth-macos-intel.dmg"


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
        self.assertRegex(text, r'dmgbuild .*-D app=dist/Hearth\.app Hearth "\$DMG"')
        self.assertIn("hdiutil attach", text)
        self.assertIn("--selftest", text)
        self.assertIn("name: ${{ matrix.dmg }}", text)
        self.assertNotIn(".zip", text)

    def test_the_selftest_runs_on_the_app_inside_the_image(self):
        text = read(".github/workflows/macos.yml")
        self.assertIn("/Volumes/Hearth/Hearth.app/Contents/MacOS/hearth --selftest", text)


class MacBuildsForBothKindsOfMacTests(unittest.TestCase):
    def matrix(self):
        text = read(".github/workflows/macos.yml")
        rows = re.findall(
            r"- name: (?P<name>macOS .+)\n\s+runner: (?P<runner>\S+)\n\s+arch: (?P<arch>\S+)\n\s+dmg: (?P<dmg>\S+)",
            text,
        )
        return {dmg: (runner, arch) for _, runner, arch, dmg in rows}

    def test_two_separate_builds_not_one_universal_app(self):
        self.assertEqual(set(self.matrix()), {DMG, INTEL_DMG})
        self.assertNotIn("target_arch", read("packaging/pyinstaller/hearth.spec"))

    def test_apple_silicon_keeps_the_plain_name_and_intel_says_intel(self):
        got = self.matrix()
        self.assertEqual(got[DMG][1], "arm64")
        self.assertEqual(got[INTEL_DMG][1], "x86_64")
        self.assertNotIn("intel", DMG)
        self.assertIn("intel", INTEL_DMG)

    def test_each_build_runs_on_a_mac_of_its_own_kind(self):
        got = self.matrix()
        self.assertEqual(got[DMG][0], "macos-latest")
        # macos-13 is retired. macos-15-intel is GitHub's last Intel label.
        self.assertEqual(got[INTEL_DMG][0], "macos-15-intel")

    def test_one_failing_build_does_not_hide_the_other(self):
        self.assertIn("fail-fast: false", read(".github/workflows/macos.yml"))

    def test_the_build_proves_it_runs_natively_and_is_the_right_kind(self):
        text = read(".github/workflows/macos.yml")
        self.assertIn('test "$(uname -m)" = "$ARCH"', text)
        self.assertIn("sysctl.proc_translated", text)
        self.assertIn('test "$(lipo -archs dist/Hearth.app/Contents/MacOS/hearth)" = "$ARCH"', text)
        self.assertIn('grep -qx "machine $ARCH" "$RUNNER_TEMP/selftest.txt"', text)
        self.assertIn('grep -qx "machine $ARCH" "$RUNNER_TEMP/selftest-dmg.txt"', text)


class BundleVersionTests(unittest.TestCase):
    def test_the_bundle_version_comes_from_the_package(self):
        text = read("packaging/pyinstaller/hearth.spec")
        self.assertIn('"CFBundleVersion": __version__', text)
        self.assertIn('"CFBundleShortVersionString": __version__', text)


if __name__ == "__main__":
    unittest.main()
