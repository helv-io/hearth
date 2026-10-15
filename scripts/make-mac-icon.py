#!/usr/bin/env python3
"""Make the macOS icon art from hearth/qml/hearth.png.

Run by hand when the artwork changes. It needs Pillow and writes two files that
are committed:

  packaging/macos/icon-1024.png   the master the CI turns into Hearth.icns
  hearth/qml/hearth-macos.png     the same picture at 512 px, for the window and
                                  Dock icon the app sets while it runs

hearth.png is a dark rounded tile on a dark square. A Mac icon needs the tile
alone, with clear space around it, which is how macOS draws every other app. So
the tile is cut out, given clean rounded corners and a soft shadow, and placed
on a transparent 1024 px canvas the way Apple's icon grid asks: an 824 px tile.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "hearth" / "qml" / "hearth.png"
CANVAS = 1024
TILE = 824
# The tile in hearth.png covers x and y 40 to 215. One pixel in is cut so none of
# the dark square around it bleeds into the new corners.
CROP = (41, 41, 215, 215)
CORNER = 0.21  # of the tile's width, measured from the corners in hearth.png


def rounded_mask(size, radius, scale=4):
    big = Image.new("L", (size * scale, size * scale), 0)
    ImageDraw.Draw(big).rounded_rectangle(
        (0, 0, size * scale - 1, size * scale - 1), radius * scale, fill=255
    )
    return big.resize((size, size), Image.LANCZOS)


def build():
    tile = Image.open(SOURCE).convert("RGB").crop(CROP).resize((TILE, TILE), Image.LANCZOS)
    mask = rounded_mask(TILE, round(TILE * CORNER))
    origin = ((CANVAS - TILE) // 2, (CANVAS - TILE) // 2)

    shadow = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 90), (origin[0], origin[1] + 10), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))

    icon = shadow
    icon.paste(tile, origin, mask)
    return icon


def main():
    icon = build()
    master = ROOT / "packaging" / "macos" / "icon-1024.png"
    master.parent.mkdir(parents=True, exist_ok=True)
    icon.save(master, optimize=True)
    icon.resize((512, 512), Image.LANCZOS).save(ROOT / "hearth" / "qml" / "hearth-macos.png", optimize=True)
    print("wrote", master)


if __name__ == "__main__":
    main()
