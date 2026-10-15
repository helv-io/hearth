#!/usr/bin/env python3
"""Regenerate the pinned, offline source lists next to the manifest.

Flathub builds without network access, so every dependency has to be named in
the manifest with a URL and a checksum. Run this after changing
requirements.txt, requirements-build.txt or the pymobiledevice3 pin below, then
commit the generated files. See docs/flathub.md.

    python3 packaging/flatpak/update-sources.py

Needs: flatpak-pip-generator.py and flatpak-cargo-generator.py from
https://github.com/flatpak/flatpak-builder-tools (set TOOLS_DIR to the clone),
the KDE 6.11 SDK installed with flatpak (pip runs inside it, so the Python
version matches the runtime), and the Python modules PyYAML, aiohttp, tomlkit,
requirements-parser and packaging.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
TOOLS = Path(os.environ.get("TOOLS_DIR", "/tmp/flatpak-builder-tools"))
RUNTIME = "org.kde.Sdk//6.11"
CARGO_ENV = {
    "append-path": "/usr/lib/sdk/rust-stable/bin",
    "env": {"CARGO_HOME": "/run/build/{name}/cargo"},
}
# pymobiledevice3 is pure Python and needs no build step, so its wheel is used.
# Its dependencies are not installed from its metadata. requirements.txt lists
# the few that the parts of it Hearth imports need.
NO_DEPS = {"pymobiledevice3": "11.31.0"}


def pypi_file(name: str, version: str, kind: str) -> dict:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json") as r:
        files = json.load(r)["urls"]
    for f in files:
        if f["packagetype"] == kind and (kind == "sdist" or f["filename"].endswith("py3-none-any.whl")):
            return {"type": "file", "url": f["url"], "sha256": f["digests"]["sha256"]}
    raise SystemExit(f"{name} {version} has no {kind}")


def pinned(path: Path) -> list[tuple[str, str]]:
    pins = []
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            name, version = line.split("==")
            pins.append((name.strip(), version.strip()))
    return pins


def download(source: dict, to: Path) -> Path:
    target = to / source["url"].rsplit("/", 1)[1]
    urllib.request.urlretrieve(source["url"], target)
    if hashlib.sha256(target.read_bytes()).hexdigest() != source["sha256"]:
        raise SystemExit(f"checksum mismatch for {target.name}")
    return target


def cargo_sources(lock: Path, out: Path) -> None:
    subprocess.run(
        [sys.executable, str(TOOLS / "cargo" / "flatpak-cargo-generator.py"), str(lock), "-o", str(out)],
        check=True,
    )


def lock_of(source: dict, work: Path) -> Path:
    archive = download(source, work)
    with tarfile.open(archive) as tar:
        member = next(m for m in tar.getmembers() if m.name.count("/") == 1 and m.name.endswith("/Cargo.lock"))
        tar.extract(member, work, filter="data")
    return work / member.name


ORDER = ["name", "buildsystem", "build-options", "build-commands", "cleanup", "sources", "modules"]


class Indented(yaml.SafeDumper):
    """Lists are indented under their key, as the Flathub manifest style asks."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def ordered(node):
    """Keys in the order of the Flathub manifest style guide."""
    if isinstance(node, dict):
        keys = sorted(node, key=lambda k: ORDER.index(k) if k in ORDER else len(ORDER))
        return {k: ordered(node[k]) for k in keys}
    if isinstance(node, list):
        return [ordered(n) for n in node]
    return node


def write(path: Path, header: str, data: dict) -> None:
    text = yaml.dump(ordered(data), Dumper=Indented, sort_keys=False, width=100)
    # A blank line between modules.
    text = text.replace("\n  - name: ", "\n\n  - name: ").replace("modules:\n\n", "modules:\n")
    path.write_text(header + text)


def main() -> None:
    work = Path(tempfile.mkdtemp())
    build = {n: pypi_file(n, v, "sdist") for n, v in pinned(HERE / "requirements-build.txt")}

    # Python dependencies, one module each, from the pinned list.
    subprocess.run(
        [
            sys.executable, str(TOOLS / "pip" / "flatpak-pip-generator.py"),
            "--runtime", RUNTIME, "--yaml",
            "-r", str(HERE / "requirements.txt"),
            "-o", str(HERE / "python3-requirements"),
        ],
        check=True,
    )
    path = HERE / "python3-requirements.yaml"
    data = yaml.safe_load(path.read_text())
    modules = []
    for module in data["modules"]:
        if module["name"] != "python3-cryptography":
            modules.append(module)
            continue
        # cryptography builds against cffi, so cffi (and pycparser) become their own,
        # earlier module. Cargo gets the vendored crates and no network.
        helpers = [s for s in module["sources"] if "/cryptography-" not in s["url"]]
        crypto = next(s for s in module["sources"] if "/cryptography-" in s["url"])
        modules.append({
            "name": "python3-cffi",
            "buildsystem": "simple",
            "build-commands": [
                'pip3 install --verbose --exists-action=i --no-index --find-links="file://${PWD}" '
                "--prefix=${FLATPAK_DEST} --no-build-isolation cffi pycparser"
            ],
            "sources": helpers,
        })
        module["build-commands"] = [c.replace("--prefix=", "--no-deps --prefix=") for c in module["build-commands"]]
        module["sources"] = [crypto, "cargo-sources-cryptography.json"]
        module["build-options"] = {
            "append-path": CARGO_ENV["append-path"],
            "env": {"CARGO_HOME": "/run/build/python3-cryptography/cargo"},
        }
        modules.append(module)
        cargo_sources(lock_of(crypto, work), HERE / "cargo-sources-cryptography.json")
    data["modules"] = modules
    write(path, "# Generated by update-sources.py. Do not edit by hand.\n", data)

    # maturin and its helpers, built from source. cryptography needs maturin.
    maturin = {
        "name": "python3-maturin",
        "buildsystem": "simple",
        "build-options": {
            "append-path": CARGO_ENV["append-path"],
            "env": {"CARGO_HOME": "/run/build/python3-maturin/cargo"},
        },
        "build-commands": [
            'pip3 install --verbose --exists-action=i --no-index --find-links="file://${PWD}" '
            '--prefix=${FLATPAK_DEST} --no-build-isolation semantic_version setuptools_rust',
            'pip3 install --verbose --exists-action=i --no-index --find-links="file://${PWD}" '
            '--prefix=${FLATPAK_DEST} --no-build-isolation maturin',
        ],
        "sources": [build["maturin"], build["setuptools-rust"], build["semantic-version"], "cargo-sources-maturin.json"],
        "cleanup": ["/bin/maturin", "/lib/python*/site-packages/maturin*", "/lib/python*/site-packages/setuptools_rust*",
                    "/lib/python*/site-packages/semantic_version*"],
    }
    cargo_sources(lock_of(build["maturin"], work), HERE / "cargo-sources-maturin.json")
    write(HERE / "python3-maturin.yaml", "# Generated by update-sources.py. Do not edit by hand.\n", maturin)

    # pymobiledevice3 itself, installed without its dependency list.
    modules = []
    for name, version in NO_DEPS.items():
        modules.append({
            "name": f"python3-{name}",
            "buildsystem": "simple",
            "build-commands": [
                'pip3 install --verbose --exists-action=i --no-index --no-deps --find-links="file://${PWD}" '
                f'--prefix=${{FLATPAK_DEST}} "{name}=={version}" --no-build-isolation'
            ],
            "sources": [pypi_file(name, version, "bdist_wheel")],
        })
    write(HERE / "python3-pymobiledevice3.yaml", "# Generated by update-sources.py. Do not edit by hand.\n",
          modules[0])


if __name__ == "__main__":
    main()
