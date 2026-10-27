#!/usr/bin/env python3
"""Draw every Hearth icon from packaging/hearth.svg.

Run by hand when the artwork changes. It needs rsvg-convert (librsvg) and Pillow.
The SVG is the picture, edge to edge, on a black square. Nothing here redraws it.

  hearth/qml/hearth.png                 that picture at 1024 px, for the sidebar
                                        and the window icon on Windows and Linux
  hearth/qml/hearth.ico                 the Windows program icon
  packaging/linux/icons/256.png         the Linux icon theme, 256 px
  packaging/linux/icons/512.png         the Linux icon theme, 512 px
  packaging/macos/icon-1024.png         the macOS master
  hearth/qml/hearth-macos.png           the same macOS picture at 512 px, for the
                                        window and Dock icon while Hearth runs

Windows and Linux use the square picture. A Mac icon needs clear space around a
rounded tile, which is how macOS draws every other app. The picture is rounded,
given a soft shadow, and placed on a transparent 1024 px canvas the way Apple's
icon grid asks: an 824 px tile. The corner radius is 0.21 of the tile.
"""

import io
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "packaging" / "hearth.svg"
CANVAS = 1024
TILE = 824
CORNER = 0.21  # of the tile's width
ICO_SIZES = (16, 32, 48, 64, 128, 256)


def render(size=CANVAS):
    tool = shutil.which("rsvg-convert")
    if tool is None:
        raise SystemExit("rsvg-convert is missing. Install librsvg.")
    if not SVG.is_file():
        raise SystemExit(f"{SVG} is missing.")
    proc = subprocess.run(
        [tool, "-w", str(size), "-h", str(size), str(SVG)],
        check=True,
        capture_output=True,
    )
    return Image.open(io.BytesIO(proc.stdout)).convert("RGB")


def rounded_mask(size, radius, scale=4):
    big = Image.new("L", (size * scale, size * scale), 0)
    ImageDraw.Draw(big).rounded_rectangle(
        (0, 0, size * scale - 1, size * scale - 1), radius * scale, fill=255
    )
    return big.resize((size, size), Image.LANCZOS)


def mac_icon(square):
    """The square picture, on the macOS icon grid. Same mask, shadow and padding as before."""
    tile = square.resize((TILE, TILE), Image.LANCZOS)
    mask = rounded_mask(TILE, round(TILE * CORNER))
    origin = ((CANVAS - TILE) // 2, (CANVAS - TILE) // 2)

    shadow = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 90), (origin[0], origin[1] + 10), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))

    icon = shadow
    icon.paste(tile, origin, mask)
    return icon


def main():
    square = render()
    qml = ROOT / "hearth" / "qml"
    square.save(qml / "hearth.png", optimize=True)
    square.save(qml / "hearth.ico", format="ICO", sizes=[(size, size) for size in ICO_SIZES])

    linux = ROOT / "packaging" / "linux" / "icons"
    linux.mkdir(parents=True, exist_ok=True)
    for size in (256, 512):
        square.resize((size, size), Image.LANCZOS).save(linux / f"{size}.png", optimize=True)

    icon = mac_icon(square)
    master = ROOT / "packaging" / "macos" / "icon-1024.png"
    master.parent.mkdir(parents=True, exist_ok=True)
    icon.save(master, optimize=True)
    icon.resize((512, 512), Image.LANCZOS).save(qml / "hearth-macos.png", optimize=True)
    print("wrote", master)


if __name__ == "__main__":
    main()
