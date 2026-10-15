#!/usr/bin/env bash
# Make the folder that goes into the flathub/io.helv.Hearth repository.
#
#   scripts/flathub-manifest.sh v0.5.0 /tmp/io.helv.Hearth
#
# It copies the manifest and the generated source lists, and swaps the working
# tree source for the release tag and the commit that tag points to. The tag
# must already be pushed. See docs/flathub.md.
set -euo pipefail

tag="${1:?usage: flathub-manifest.sh vX.Y.Z output-dir}"
out="${2:?usage: flathub-manifest.sh vX.Y.Z output-dir}"
repo="https://github.com/helv-io/hearth.git"
here="$(cd "$(dirname "$0")/.." && pwd)"
src="$here/packaging/flatpak"

commit="$(git ls-remote "$repo" "refs/tags/$tag^{}" | cut -f1)"
if [ -z "$commit" ]; then
  commit="$(git ls-remote "$repo" "refs/tags/$tag" | cut -f1)"
fi
[ -n "$commit" ] || { echo "tag $tag is not on $repo" >&2; exit 1; }

mkdir -p "$out"
cp "$src"/python3-*.yaml "$src"/cargo-sources-*.json "$out"/
python3 - "$src/io.helv.Hearth.yml" "$out/io.helv.Hearth.yml" "$repo" "$tag" "$commit" <<'PY'
import sys

source, target, repo, tag, commit = sys.argv[1:]
text = open(source, encoding="utf-8").read()
old = "      - type: dir\n        path: ../..\n        skip:\n          - .git\n          - .flatpak-builder\n          - build\n          - repo\n"
new = f"      - type: git\n        url: {repo}\n        tag: {tag}\n        commit: {commit}\n"
if old not in text:
    sys.exit("the hearth source block was not found in the manifest")
text = text.replace(old, new)
lines = text.splitlines(keepends=True)
start = next(n for n, line in enumerate(lines) if line.startswith("app-id:"))
note = "# Generated from packaging/flatpak in helv-io/hearth by scripts/flathub-manifest.sh.\n"
open(target, "w", encoding="utf-8").write(note + "".join(lines[start:]))
PY
echo "wrote $out for $tag at $commit"
