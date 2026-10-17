#!/usr/bin/env python3
"""Prove, on any machine, that every build target can install Hearth's dependencies from ready-made wheels.

Why: cryptography 50 has no Intel Mac wheel. pip then compiled it on the Intel runner against an old OpenSSL, and three
macOS builds in a row failed before anyone found out why (0e3c7a2, 09902c5, a6bf55d). This asks pip the same question for
each target without owning that kind of computer, in seconds, and names the package that has no wheel.

usage: scripts/check-wheels.py [extra requirement ...]
  An extra requirement is added to the install, to try a pin before committing it: scripts/check-wheels.py cryptography==50.0.2
"""
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = "3.12"  # the Python the build workflows use
# What the build workflows install next to Hearth's own dependencies.
BUILD_TOOLS = ["pyinstaller"]
TARGETS = {
    "macOS Apple silicon": ["macosx_14_0_arm64", "macosx_11_0_arm64", "macosx_11_0_universal2"],
    "macOS Intel": ["macosx_15_0_x86_64", "macosx_10_15_x86_64", "macosx_10_9_x86_64", "macosx_10_9_universal2"],
    "Windows": ["win_amd64"],
}


def requirements() -> list[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return list(data["project"]["dependencies"]) + BUILD_TOOLS + sys.argv[1:]


def check(name: str, platforms: list[str]) -> bool:
    with tempfile.TemporaryDirectory() as target:
        command = [
            sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed", "--quiet",
            "--no-input", "--disable-pip-version-check", "--only-binary=:all:", "--target", target,
            "--python-version", PYTHON, "--implementation", "cp", "--abi", "cp" + PYTHON.replace(".", ""),
        ]
        for platform in platforms:
            command += ["--platform", platform]
        run = subprocess.run(command + requirements(), capture_output=True, text=True)
    if run.returncode == 0:
        print(f"ok   {name}")
        return True
    text = run.stderr + run.stdout
    lines = [line.strip() for line in text.splitlines() if "No matching distribution" in line or "no versions of" in line.lower()
             or "depends on" in line or "conflict" in line.lower()]
    why = " ".join(lines[:3]) or text.strip().splitlines()[-1]
    print(f"FAIL {name}: part of the install has no ready-made wheel for this target. {why[:300]}")
    print("     Pin the package to a version that has a wheel for this target, or replace it.")
    return False


def main() -> int:
    results = [check(name, platforms) for name, platforms in TARGETS.items()]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
