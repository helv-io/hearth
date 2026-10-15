"""Home-screen shapes for the iPhones and iPads that still get OS updates.

iOS 26 starts at iPhone 11 and iPhone SE (2nd generation). iPadOS 26 starts at
the 2018 iPad Pros, iPad Air (3rd), iPad mini (5th), and iPad (8th). A model
older than that still opens, with a warning. An unknown future model opens on
the family grid. The icon list does not carry the grid size, so the editor
picks one.

iPad widget spans and portrait-versus-landscape order are not in the icon
list either. An iPad uses the same widget sizes as an iPhone until that is
known. The iPad dock here is the pinned side only, capped at 15.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Screen:
    family: str
    columns: int
    rows: int
    dock: int
    chassis_w: float
    chassis_h: float
    island: bool
    label: str
    product: str = ""
    warning: str = ""


# iPhone 15 Pro Max body is 76.7 × 159.9 mm. 390 × 812 keeps that ratio.
IPHONE = Screen("iphone", 4, 6, 4, 390, 812, True, "iPhone")

# Landscape More grid, 6 × 5. The chassis is a stage size, not one model's millimeters.
IPAD = Screen("ipad", 6, 5, 15, 744, 520, False, "iPad")

_DROPPED = (
    "This model is too old for the current OS. A read still works. "
    "A send can be ignored on a device Apple no longer updates."
)


def for_device(product_type: str = "", device_class: str = "") -> Screen:
    """Pick a grid. Never refuse a device that lockdown can see."""
    product = (product_type or "").strip()
    kind = (device_class or "").strip().lower()
    ipad = kind == "ipad" or product.startswith("iPad")
    iphone = kind == "iphone" or product.startswith("iPhone")
    if ipad and not (iphone and kind == "iphone"):
        base = IPAD
        warning = _DROPPED if _old_ipad(product) else ""
    elif iphone or kind in ("", "iphone"):
        base = IPHONE
        warning = _DROPPED if _old_iphone(product) else ""
    else:
        base = IPHONE
        warning = "This is not an iPhone or iPad. The grid shown is the iPhone grid."
    if product == base.product and warning == base.warning:
        return base
    return replace(base, product=product, warning=warning)


def from_note(note: dict | None) -> Screen:
    """A version saved before screens existed opens as an iPhone."""
    if not isinstance(note, dict):
        return IPHONE
    raw = note.get("screen")
    if not isinstance(raw, dict):
        return IPHONE
    family = str(raw.get("family") or "")
    product = str(raw.get("product") or "")
    base = IPAD if family == "ipad" else IPHONE
    if family not in ("iphone", "ipad"):
        return for_device(product, "")
    return replace(
        base,
        columns=_positive(raw.get("columns"), base.columns),
        rows=_positive(raw.get("rows"), base.rows),
        dock=_positive(raw.get("dock"), base.dock),
        product=product,
    )


def with_dock(screen: Screen, count: int) -> Screen:
    """Show every dock icon the phone already has, even past the usual cap."""
    slots = max(screen.dock, int(count or 0))
    if slots == screen.dock:
        return screen
    return replace(screen, dock=slots)


def note_fields(screen: Screen) -> dict:
    return {
        "family": screen.family,
        "columns": screen.columns,
        "rows": screen.rows,
        "dock": screen.dock,
        "product": screen.product,
    }


def _positive(value, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return number if number > 0 else fallback


def _major(product: str, prefix: str) -> int | None:
    if not product.startswith(prefix):
        return None
    number = product[len(prefix):].split(",", 1)[0]
    return int(number) if number.isdigit() else None


def _old_iphone(product: str) -> bool:
    # iPhone11,* is XS / XR. iPhone 11 and SE (2nd) are iPhone12,*.
    major = _major(product, "iPhone")
    return major is not None and major <= 11


def _old_ipad(product: str) -> bool:
    # iPad7,* includes the 7th-generation iPad. iPad8,* is the first supported Pro.
    major = _major(product, "iPad")
    return major is not None and major <= 7
