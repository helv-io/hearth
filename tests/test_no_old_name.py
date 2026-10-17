"""The old program name is gone for good. Only the changelog may mention it, because it tells what past releases did."""

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Built from pieces so this file does not contain the name it forbids.
OLD_NAME = re.compile("iphone" + r"[-_ .]?" + "layout", re.IGNORECASE)
ALLOWED = {"CHANGELOG.md"}


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    return [name for name in out.split("\0") if name]


class OldNameTests(unittest.TestCase):
    def test_no_file_name_uses_the_old_name(self):
        bad = [name for name in tracked_files() if OLD_NAME.search(name)]
        self.assertEqual(bad, [], "a file is named with the old program name")

    def test_no_file_text_uses_the_old_name_except_the_changelog(self):
        found = []
        for name in tracked_files():
            if name in ALLOWED or not (ROOT / name).is_file():
                continue
            try:
                text = (ROOT / name).read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if OLD_NAME.search(line):
                    found.append(f"{name}:{number}")
        self.assertEqual(found, [], "the old program name is back. Use Hearth, hearth, or Hearth/<version>")

    def test_the_old_data_folder_is_not_looked_for(self):
        text = (ROOT / "hearth" / "paths.py").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"(?i)legacy")


if __name__ == "__main__":
    unittest.main()
