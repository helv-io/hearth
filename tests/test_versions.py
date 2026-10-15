import os
import plistlib
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from hearth import device


def _screen(order):
    def icon(name):
        return {
            "bundleIdentifier": f"com.example.{name}",
            "displayName": name,
            "bundleVersion": "1",
            "iconModDate": datetime(2026, 1, 1),
        }

    dock = [icon("phone")]
    page = [icon(name) for name in order]
    return [dock, page]


def _write(folder: Path, name: str, state, when: int) -> Path:
    path = folder / name
    path.write_bytes(plistlib.dumps(state, fmt=plistlib.FMT_BINARY))
    path.with_suffix(".json").write_text('{"reason": "pull"}\n', encoding="utf-8")
    os.utime(path, (when, when))
    os.utime(path.with_suffix(".json"), (when, when))
    return path


class VersionCollapseTests(unittest.TestCase):
    def test_matching_neighbors_keep_the_earliest(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            first = _write(folder, "20261014-120000-pull.plist", _screen(["a", "b"]), 100)
            middle = _write(folder, "20261014-120100-pull.plist", _screen(["a", "b"]), 200)
            later = _write(folder, "20261014-120200-pushed.plist", _screen(["a", "b"]), 300)
            other = _write(folder, "20261014-120300-pull.plist", _screen(["b", "a"]), 400)

            device.collapse_versions(folder)

            names = sorted(path.name for path in folder.glob("*.plist"))
            self.assertEqual(names, [first.name, other.name])
            self.assertFalse(middle.exists())
            self.assertFalse(middle.with_suffix(".json").exists())
            self.assertFalse(later.exists())
            self.assertTrue(first.with_suffix(".json").exists())
            self.assertTrue(other.with_suffix(".json").exists())

    def test_a_layout_that_returns_later_stays(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _write(folder, "20261014-120000-pull.plist", _screen(["a"]), 100)
            _write(folder, "20261014-120100-pull.plist", _screen(["b"]), 200)
            _write(folder, "20261014-120200-pull.plist", _screen(["a"]), 300)

            device.collapse_versions(folder)

            self.assertEqual(len(list(folder.glob("*.plist"))), 3)

    def test_an_icon_date_is_not_a_new_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            changed = _screen(["a"])
            changed[1][0]["iconModDate"] = datetime(2026, 6, 1)
            changed[1][0]["bundleVersion"] = "9"
            _write(folder, "20261014-120000-pull.plist", _screen(["a"]), 100)
            _write(folder, "20261014-120100-pull.plist", changed, 200)

            device.collapse_versions(folder)

            self.assertEqual([path.name for path in folder.glob("*.plist")], ["20261014-120000-pull.plist"])

    def test_a_different_widget_stays(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)

            def widget(name):
                return [{
                    "elementType": "widget",
                    "bundleIdentifier": "com.example.widgets",
                    "widgetIdentifier": name,
                    "gridSize": "small",
                }]

            _write(folder, "20261014-120000-pull.plist", [[], widget("one")], 100)
            _write(folder, "20261014-120100-pull.plist", [[], widget("two")], 200)

            device.collapse_versions(folder)

            self.assertEqual(len(list(folder.glob("*.plist"))), 2)

    def test_an_unreadable_file_is_kept_and_splits_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _write(folder, "20261014-120000-pull.plist", _screen(["a"]), 100)
            broken = folder / "20261014-120100-pull.plist"
            broken.write_bytes(b"not a plist")
            os.utime(broken, (200, 200))
            _write(folder, "20261014-120200-pull.plist", _screen(["a"]), 300)

            device.collapse_versions(folder)

            self.assertEqual(len(list(folder.glob("*.plist"))), 3)
            self.assertTrue(broken.exists())

    def test_listing_collapses_before_it_returns_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _write(folder, "20261014-120000-pull.plist", _screen(["a", "b"]), 100)
            _write(folder, "20261014-120100-pull.plist", _screen(["a", "b"]), 200)
            _write(folder, "20261014-120200-pull.plist", _screen(["b"]), 300)
            with patch("hearth.device.version_dir", return_value=folder):
                rows = device.list_versions()

            self.assertEqual(
                [Path(row["path"]).name for row in rows],
                ["20261014-120200-pull.plist", "20261014-120000-pull.plist"],
            )
            self.assertFalse((folder / "20261014-120100-pull.plist").exists())


if __name__ == "__main__":
    unittest.main()
