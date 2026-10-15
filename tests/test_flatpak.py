import re
import tomllib
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from hearth import __version__

ROOT = Path(__file__).resolve().parents[1]
FLATPAK = ROOT / "packaging/flatpak"
METAINFO = ROOT / "packaging/linux/io.helv.Hearth.metainfo.xml"
DESKTOP = ROOT / "packaging/linux/io.helv.Hearth.desktop"
APP_ID = "io.helv.Hearth"


def manifest() -> str:
    return (FLATPAK / f"{APP_ID}.yml").read_text(encoding="utf-8")


def modules() -> list[str]:
    """Every module file the manifest includes, read as text."""
    names = re.findall(r"^  - (python3-[\w.-]+\.yaml)$", manifest(), re.MULTILINE)
    return [(FLATPAK / name).read_text(encoding="utf-8") for name in names]


class ManifestTests(unittest.TestCase):
    def test_the_build_itself_asks_for_no_network(self):
        text = manifest()
        self.assertNotIn("build-args", text)
        self.assertNotIn("--share=network\n    build-commands", text)
        for module in [text, *modules()]:
            self.assertNotRegex(module, r"\bgit clone\b|\bcurl\b|\bwget\b")

    def test_every_pip_install_is_offline(self):
        for text in [manifest(), *modules()]:
            for command in re.findall(r"pip3 install.*?(?=\n\s*-|\n\S|\Z)", text, re.DOTALL):
                self.assertIn("--no-index", command, command)

    def test_every_downloaded_file_is_pinned_by_checksum(self):
        for text in modules():
            urls = re.findall(r"^\s*(?:- )?url: (\S+)$", text, re.MULTILINE)
            sums = re.findall(r"^\s*sha256: ([0-9a-f]{64})$", text, re.MULTILINE)
            self.assertTrue(urls)
            self.assertEqual(len(urls), len(sums))
            for url in urls:
                self.assertTrue(url.startswith("https://"), url)

    def test_the_cargo_crates_are_pinned_by_checksum_too(self):
        for path in FLATPAK.glob("cargo-sources-*.json"):
            text = path.read_text(encoding="utf-8")
            self.assertEqual(text.count('"url"'), text.count('"sha256"'), path.name)

    def test_the_requirements_are_exact_pins(self):
        for name in ("requirements.txt", "requirements-build.txt"):
            lines = [x.split("#")[0].strip() for x in (FLATPAK / name).read_text(encoding="utf-8").splitlines()]
            for line in filter(None, lines):
                self.assertRegex(line, r"^[A-Za-z0-9_.-]+==[0-9][\w.]*$", line)

    def test_pyside_comes_from_the_base_app_not_a_pip_wheel(self):
        text = manifest()
        self.assertIn("base: io.qt.PySide.BaseApp", text)
        self.assertNotRegex("\n".join(modules()).lower(), r"pyside6|shiboken")

    def test_the_sandbox_cannot_run_commands_on_the_computer(self):
        text = manifest()
        self.assertNotIn("org.freedesktop.Flatpak", text)
        self.assertNotIn("--device=all", text)
        self.assertNotIn("--filesystem=host", text)
        self.assertNotIn("--filesystem=home", text)

    def test_the_usb_service_socket_is_the_only_file_access(self):
        self.assertEqual(re.findall(r"--filesystem=(\S+)", manifest()), ["/run/usbmuxd"])

    def test_the_command_and_the_app_id_match_the_package(self):
        text = manifest()
        self.assertIn(f"app-id: {APP_ID}", text)
        self.assertIn("command: hearth", text)
        scripts = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
        self.assertIn("hearth", scripts)


class MetainfoTests(unittest.TestCase):
    def setUp(self):
        self.root = ET.parse(METAINFO).getroot()

    def test_the_id_is_the_app_id_and_the_desktop_file_matches(self):
        self.assertEqual(self.root.findtext("id"), APP_ID)
        self.assertEqual(self.root.findtext("launchable"), f"{APP_ID}.desktop")
        self.assertTrue(DESKTOP.is_file())
        self.assertIn(f"Icon={APP_ID}", DESKTOP.read_text(encoding="utf-8"))

    def test_the_license_says_what_the_files_say(self):
        self.assertEqual(self.root.findtext("project_license"), "GPL-3.0-or-later")
        self.assertIn("GPL-3.0-or-later", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("GNU GENERAL PUBLIC LICENSE", (ROOT / "LICENSE").read_text(encoding="utf-8"))

    def test_the_summary_fits_flathubs_limit(self):
        self.assertLessEqual(len(self.root.findtext("summary")), 35)
        self.assertFalse(self.root.findtext("summary").endswith("."))

    def test_there_is_a_developer_and_a_content_rating(self):
        self.assertTrue(self.root.findtext("developer/name"))
        self.assertEqual(self.root.find("content_rating").get("type"), "oars-1.1")

    def test_screenshots_are_raw_github_images_on_this_versions_tag(self):
        images = [i.text for i in self.root.iterfind("screenshots/screenshot/image")]
        self.assertGreaterEqual(len(images), 1)
        for url in images:
            match = re.fullmatch(r"https://raw\.githubusercontent\.com/helv-io/hearth/v([\d.]+)/(docs/images/\w+\.png)", url)
            self.assertIsNotNone(match, url)
            self.assertEqual(match.group(1), __version__, "bump the screenshot tags with the version")
            self.assertTrue((ROOT / match.group(2)).is_file(), url)
        self.assertEqual(len(self.root.findall("screenshots/screenshot[@type='default']")), 1)
        for caption in self.root.iterfind("screenshots/screenshot/caption"):
            self.assertFalse(caption.text.endswith("."))

    def test_every_release_has_a_date_and_a_details_link(self):
        for release in self.root.iterfind("releases/release"):
            self.assertRegex(release.get("date"), r"^\d{4}-\d{2}-\d{2}$")
            self.assertEqual(
                release.findtext("url"),
                f"https://github.com/helv-io/hearth/releases/tag/v{release.get('version')}",
            )

    def test_the_icon_is_big_enough_and_installed_by_the_manifest(self):
        from struct import unpack

        data = (ROOT / "hearth/qml/hearth.png").read_bytes()
        width, height = unpack(">II", data[16:24])
        self.assertGreaterEqual(min(width, height), 128)
        self.assertIn(f"icons/hicolor/{width}x{height}/apps/{APP_ID}.png", manifest())
