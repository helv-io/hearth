#!/bin/sh
# Builds packaging/macos/Hearth.icns from packaging/macos/icon-1024.png.
# Needs sips and iconutil, which every Mac has, so it runs on the CI runner.
# The master comes from scripts/make-mac-icon.py.
set -eu

here="$(cd "$(dirname "$0")" && pwd)"
master="$here/icon-1024.png"
set_dir="$here/Hearth.iconset"
out="$here/Hearth.icns"

test -f "$master"
rm -rf "$set_dir" "$out"
mkdir "$set_dir"

# Every size macOS asks for: 16 to 512, each with an @2x twin that is twice the pixels.
for size in 16 32 128 256 512; do
  double=$((size * 2))
  sips -z "$size" "$size" "$master" --out "$set_dir/icon_${size}x${size}.png" >/dev/null
  sips -z "$double" "$double" "$master" --out "$set_dir/icon_${size}x${size}@2x.png" >/dev/null
done

iconutil -c icns "$set_dir" -o "$out"
rm -rf "$set_dir"
test -s "$out"
echo "wrote $out ($(wc -c < "$out" | tr -d ' ') bytes)"
