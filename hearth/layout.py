"""Home-screen document: packing, dragging, and applying an organizer proposal.

The icon state is the list SpringBoard returns. Item 0 is the dock. Every later
item is a page. A page keeps each icon on the cell where it was placed, so a
gap stays empty. Folders still pack tight: nine apps to a page, and no gaps.
Folders and widgets are the original dictionaries, moved around rather than
rebuilt, so a web clip keeps its URL and a widget keeps its id.

`_row` and `_col` are editor coordinates. Strip them before a push. A saved
icon list from the phone has no empty-cell marker, so a push closes gaps.
"""

from __future__ import annotations

import json
from typing import Any

from hearth.screens import IPHONE, Screen

COLUMNS = 4
ROWS = 6
FOLDER_SLOTS = 9
DOCK_SLOTS = 4
POS_ROW = "_row"
POS_COL = "_col"

_screen: Screen = IPHONE


def active_screen() -> Screen:
    return _screen


def set_screen(screen: Screen) -> None:
    """The grid used when a call does not pass columns and rows."""
    global _screen
    _screen = screen

WIDGET_SPAN = {
    "small": (2, 2),
    "medium": (4, 2),
    "large": (4, 4),
    "extralarge": (4, 4),
}

Item = dict[str, Any]
State = list[list[Item]]


def ident(icon: Item) -> str:
    if not isinstance(icon, dict):
        return ""
    if icon.get("webClipURL"):
        return str(icon.get("displayIdentifier") or "")
    return str(icon.get("bundleIdentifier") or icon.get("displayIdentifier") or "")


def is_widget(item: Any) -> bool:
    return isinstance(item, dict) and item.get("elementType") == "widget"


def is_folder(item: Any) -> bool:
    return isinstance(item, dict) and item.get("listType") == "folder" and not is_widget(item)


def is_clip(item: Any) -> bool:
    return isinstance(item, dict) and bool(item.get("webClipURL"))


def span(item: Item) -> tuple[int, int]:
    if is_widget(item):
        key = str(item.get("gridSize") or "small").replace("-", "").lower()
        return WIDGET_SPAN.get(key, (2, 2))
    return (1, 1)


def cells_for(item: Item) -> int:
    width, height = span(item)
    return width * height


def label(item: Item) -> str:
    name = str(item.get("displayName") or "").strip()
    if name:
        return name
    if is_widget(item):
        raw = str(item.get("widgetIdentifier") or item.get("bundleIdentifier") or "Widget")
        tail = raw.split(".")[-1]
        for suffix in ("WidgetModern", "Widget", "Modern"):
            if tail.endswith(suffix) and len(tail) > len(suffix):
                tail = tail[: -len(suffix)]
        return tail or "Widget"
    return ident(item) or "Item"


def kind_of(item: Item) -> str:
    if is_widget(item):
        return "widget"
    if is_folder(item):
        return "folder"
    if is_clip(item):
        return "shortcut"
    return "app"


def flatten_folder(folder: Item) -> list[Item]:
    icons: list[Item] = []
    for page in folder.get("iconLists") or []:
        for icon in page:
            if isinstance(icon, dict):
                icons.append(icon)
    return icons


def folder_page_count(folder: Item) -> int:
    """Pages that actually hold an icon. An empty trailing page does not count."""
    count = 0
    for page in folder.get("iconLists") or []:
        if isinstance(page, list) and any(isinstance(icon, dict) for icon in page):
            count += 1
    return count


def walk_icons(state: State) -> list[Item]:
    found: list[Item] = []
    for page in state:
        for item in page:
            if is_folder(item):
                found.extend(flatten_folder(item))
            elif isinstance(item, dict):
                found.append(item)
    return found


def idents(state: State) -> list[str]:
    return [ident(icon) for icon in walk_icons(state) if ident(icon)]


def find(state: State, obj: Item) -> tuple | None:
    for index, item in enumerate(state[0]):
        if item is obj:
            return ("dock", index)
    for page_index, page in enumerate(state[1:]):
        for index, item in enumerate(page):
            if item is obj:
                return ("page", page_index, index)
            if is_folder(item):
                flat = 0
                for folder_page, icons in enumerate(item.get("iconLists") or []):
                    for folder_index, icon in enumerate(icons):
                        if icon is obj:
                            return ("folder", page_index, index, folder_page, folder_index, flat)
                        flat += 1
    return None


def _object_at(state: State, ref: str) -> Item:
    parts = ref.split(":")
    head = parts[0]
    if head == "dock":
        return state[0][int(parts[1])]
    if head == "page":
        return state[int(parts[1]) + 1][int(parts[2])]
    if head == "folder":
        folder = state[int(parts[1]) + 1][int(parts[2])]
        return folder["iconLists"][int(parts[3])][int(parts[4])]
    raise KeyError(ref)


def detach(state: State, obj: Item) -> None:
    loc = find(state, obj)
    if loc is None:
        raise KeyError("item is not on the home screen")
    if loc[0] == "dock":
        state[0].pop(loc[1])
        return
    if loc[0] == "page":
        page = state[loc[1] + 1]
        _commit_positions(page)
        page.pop(loc[2])
        return
    _page, index, folder_page, folder_index = loc[1], loc[2], loc[3], loc[4]
    page = state[_page + 1]
    _commit_positions(page)
    folder = page[index]
    folder["iconLists"][folder_page].pop(folder_index)
    folder["iconLists"] = [folder_page for folder_page in folder["iconLists"] if folder_page]
    if not flatten_folder(folder):
        page.pop(index)


def _replace(state: State, old: Item, new: Item) -> None:
    loc = find(state, old)
    if loc is None or loc[0] == "folder":
        raise KeyError("only an icon on a page or the dock can become a folder")
    if loc[0] == "dock":
        state[0][loc[1]] = new
        return
    page = state[loc[1] + 1]
    _commit_positions(page)
    if POS_ROW in old and POS_COL in old:
        new[POS_ROW] = old[POS_ROW]
        new[POS_COL] = old[POS_COL]
    page[loc[2]] = new


def _insert_on_list(items: list[Item], anchor: Item | None, obj: Item) -> None:
    if anchor is None:
        items.append(obj)
        return
    for index, item in enumerate(items):
        if item is anchor:
            items.insert(index, obj)
            return
    items.append(obj)


def _append_folder(folder: Item, obj: Item) -> None:
    pages = folder.setdefault("iconLists", [])
    if not pages or len(pages[-1]) >= FOLDER_SLOTS:
        pages.append([])
    pages[-1].append(obj)


def _rechunk(folder: Item, apps: list[Item]) -> None:
    if not apps:
        folder["iconLists"] = [[]]
        return
    folder["iconLists"] = [apps[start : start + FOLDER_SLOTS] for start in range(0, len(apps), FOLDER_SLOTS)]


def _displace_dock(state: State) -> None:
    while len(state[0]) > active_screen().dock:
        extra = state[0].pop()
        if len(state) < 2:
            state.append([])
        error, updates = _plan(state[1], extra, 0, 0)
        if error or updates is None:
            state[1].insert(0, extra)
            continue
        _apply(state[1], extra, updates)


def _reject_dock(obj: Item) -> str | None:
    if is_widget(obj):
        return "The dock takes apps and shortcuts."
    if is_folder(obj) and active_screen().family != "ipad":
        return "The dock takes apps and shortcuts."
    return None


def move(state: State, source: str, target: str) -> str | None:
    """Move one item. Returns an error message, or None when the document changed."""
    try:
        src = _object_at(state, source)
    except (KeyError, IndexError, ValueError):
        return "That icon is no longer there."
    head, _, rest = target.partition(":")
    try:
        if head == "at":
            return _move_at(state, src, rest)
        if head == "into":
            return _move_into(state, src, rest)
        if head == "onto":
            return _move_onto(state, src, rest)
    except (KeyError, IndexError, ValueError):
        return "Drop that icon again."
    return "Unknown drop."


def _move_at(state: State, src: Item, rest: str) -> str | None:
    kind, _, tail = rest.partition(":")
    if kind == "dock":
        blocked = _reject_dock(src)
        if blocked:
            return blocked
        index_text = tail
        items = state[0]
        anchor = None if index_text == "end" or int(index_text) >= len(items) else items[int(index_text)]
        if anchor is src:
            return None
        if anchor is None and items and items[-1] is src and (found := find(state, src)) and found[0] == "dock":
            return None
        detach(state, src)
        _insert_on_list(state[0], anchor, src)
        _displace_dock(state)
        return None
    if kind == "page":
        page_text, _, index_text = tail.partition(":")
        page = state[int(page_text) + 1]
        spot = _page_spot(page, src, index_text)
        if spot is None:
            return None
        if spot == "full":
            return "That page is full."
        row, col = spot
        error, updates = _plan(page, src, row, col)
        if error or updates is None:
            return error or "That page is full."
        detach(state, src)
        _apply(page, src, updates)
        return None
    if kind == "folder":
        page_text, item_text, index_text = tail.split(":")
        folder = state[int(page_text) + 1][int(item_text)]
        if not is_folder(folder):
            return "Not a folder."
        if is_widget(src) or is_folder(src):
            return "Widgets and folders stay on the page."
        flat = flatten_folder(folder)
        anchor = None if index_text == "end" or int(index_text) >= len(flat) else flat[int(index_text)]
        if anchor is src:
            return None
        # The only icon in a folder has nowhere to move inside it. Detach would
        # delete the folder and then fail to put the icon back.
        if flat and all(icon is src for icon in flat):
            return None
        detach(state, src)
        if find(state, folder) is None:
            return "That folder is empty."
        apps = [icon for icon in flatten_folder(folder) if icon is not src]
        insert_at = len(apps) if anchor is None else next(i for i, icon in enumerate(apps) if icon is anchor)
        apps.insert(insert_at, src)
        _rechunk(folder, apps)
        return None
    return "Unknown drop."


def _move_into(state: State, src: Item, rest: str) -> str | None:
    if is_widget(src) or is_folder(src):
        return "Widgets and folders stay on the page."
    folder = _object_at(state, "page:" + rest)
    if not is_folder(folder) or folder is src:
        return "Drop apps onto a folder."
    detach(state, src)
    if find(state, folder) is None:
        return "That folder is empty."
    _append_folder(folder, src)
    return None


def _move_onto(state: State, src: Item, rest: str) -> str | None:
    dst = _object_at(state, "page:" + rest)
    if dst is src:
        return None
    if is_folder(dst):
        return _move_into(state, src, rest)
    if is_widget(src) or is_widget(dst) or is_folder(src):
        return "Group apps together. Widgets stay on the page."
    detach(state, src)
    if find(state, dst) is None:
        return "That icon moved."
    _replace(state, dst, {"listType": "folder", "displayName": "Folder", "iconLists": [[dst, src]]})
    return None


def rename_folder(state: State, source: str, name: str) -> str | None:
    try:
        folder = _object_at(state, source)
    except (KeyError, IndexError, ValueError):
        return "That folder is no longer there."
    if not is_folder(folder):
        return "That is not a folder."
    cleaned = " ".join(name.split())
    if not cleaned:
        return "A folder needs a name."
    folder["displayName"] = cleaned[:80]
    return None


def add_page(state: State) -> None:
    state.append([])


def delete_page(state: State, page_index: int) -> str | None:
    pages = state[1:]
    if page_index < 0 or page_index >= len(pages):
        return "That page is gone."
    if pages[page_index]:
        return "Move everything off this page first."
    if len(pages) <= 1:
        return "Keep at least one page."
    del state[page_index + 1]
    return None


def strip_empty_pages(state: State) -> None:
    dock = state[0]
    pages = [page for page in state[1:] if page]
    if not pages:
        pages = [[]]
    state[:] = [dock, *pages]


def _has_pos(item: Item) -> bool:
    return POS_ROW in item and POS_COL in item


def _rect_free(grid, row: int, col: int, width: int, height: int) -> bool:
    rows = len(grid)
    columns = len(grid[0]) if grid else 0
    if row < 0 or col < 0 or row + height > rows or col + width > columns:
        return False
    return all(grid[r][c] is None for r in range(row, row + height) for c in range(col, col + width))


def _paint(grid, row: int, col: int, width: int, height: int, mark) -> None:
    for r in range(row, row + height):
        for c in range(col, col + width):
            grid[r][c] = mark


def _positions_of(
    items: list[Item], columns: int | None = None, rows: int | None = None
) -> dict[int, tuple[int, int]]:
    """Cell origin of each item. A page with no coordinates still packs from the top-left."""
    columns = active_screen().columns if columns is None else columns
    rows = active_screen().rows if rows is None else rows
    if not items:
        return {}
    if all(_has_pos(item) for item in items):
        return {id(item): (int(item[POS_ROW]), int(item[POS_COL])) for item in items}
    if any(_has_pos(item) for item in items):
        placed = {id(item): (int(item[POS_ROW]), int(item[POS_COL])) for item in items if _has_pos(item)}
        missing = [item for item in items if id(item) not in placed]
        height = rows
        for item, (row, col) in ((item, placed[id(item)]) for item in items if id(item) in placed):
            height = max(height, row + span(item)[1])
        for extra in range(len(missing) + 2):
            grid_rows = height + extra
            grid = [[None for _ in range(columns)] for _ in range(grid_rows)]
            fits = True
            for item in items:
                if id(item) not in placed:
                    continue
                row, col = placed[id(item)]
                width, tall = span(item)
                if not _rect_free(grid, row, col, width, tall):
                    fits = False
                    break
                _paint(grid, row, col, width, tall, id(item))
            if not fits:
                continue
            cursor = 0
            for item in missing:
                width, tall = span(item)
                found = None
                pos = cursor
                while pos < grid_rows * columns:
                    row, col = divmod(pos, columns)
                    if _rect_free(grid, row, col, width, tall):
                        found = (row, col)
                        break
                    pos += 1
                if found is None:
                    fits = False
                    break
                placed[id(item)] = found
                _paint(grid, found[0], found[1], width, tall, id(item))
                cursor = found[0] * columns + found[1] + 1
            if fits and all(id(item) in placed for item in items):
                return {id(item): placed[id(item)] for item in items}
            placed = {id(item): (int(item[POS_ROW]), int(item[POS_COL])) for item in items if _has_pos(item)}
    fitted = pack(items, columns, rows) or pack(items, columns, rows + len(items) + 2)
    if fitted is None:
        return {id(item): (index, 0) for index, item in enumerate(items)}
    placements, _grid = fitted
    return {id(items[place["index"]]): (place["row"], place["col"]) for place in placements}


def _commit_positions(items: list[Item]) -> None:
    positions = _positions_of(items)
    for item in items:
        row, col = positions[id(item)]
        item[POS_ROW] = row
        item[POS_COL] = col


def _drops_folder(item: Item, src: Item) -> bool:
    if item is src or not is_folder(item):
        return False
    icons = flatten_folder(item)
    return bool(icons) and all(icon is src for icon in icons)


def _covered(item: Item, origin: tuple[int, int]) -> set[tuple[int, int]]:
    row, col = origin
    width, height = span(item)
    return {(r, c) for r in range(row, row + height) for c in range(col, col + width)}


def _overlaps(origin: tuple[int, int], item: Item, row: int, col: int, width: int, height: int) -> bool:
    item_row, item_col = origin
    item_w, item_h = span(item)
    return item_row < row + height and row < item_row + item_h and item_col < col + width and col < item_col + item_w


def _limit_for(others: list[Item], pos: dict[int, tuple[int, int]], row: int, height: int) -> int:
    limit = active_screen().rows
    for item in others:
        origin_row, _origin_col = pos[id(item)]
        limit = max(limit, origin_row + span(item)[1])
    return max(limit, row + height)


def _fits_on(limit: int, row: int, col: int, width: int, height: int, grown: bool) -> str | None:
    if row < 0 or col < 0 or col + width > active_screen().columns:
        return "That spot is off the page."
    if row + height > active_screen().rows and not grown:
        return "That spot is off the page."
    if row + height > limit:
        return "That spot is off the page."
    return None


def _plan(page: list[Item], src: Item, row: int, col: int) -> tuple[str | None, dict[int, tuple[int, int]] | None]:
    """Decide coordinates for `src` at (row, col). An empty cell keeps every other icon."""
    width, height = span(src)
    columns = active_screen().columns
    rows = active_screen().rows
    positions = _positions_of(page)
    others = [item for item in page if item is not src and not _drops_folder(item, src)]
    pos = {id(item): positions[id(item)] for item in others}
    grown = any(pos[id(item)][0] + span(item)[1] > rows for item in others)
    limit = _limit_for(others, pos, row, height) if grown else max(rows, row + height)
    blocked = _fits_on(limit, row, col, width, height, grown)
    if blocked:
        return blocked, None

    def free(at_row: int, at_col: int, at_w: int, at_h: int, ignore: set[int]) -> bool:
        if at_row < 0 or at_col < 0 or at_col + at_w > columns or at_row + at_h > limit:
            return False
        claim = {(r, c) for r in range(at_row, at_row + at_h) for c in range(at_col, at_col + at_w)}
        for item in others:
            if id(item) in ignore:
                continue
            if claim & _covered(item, pos[id(item)]):
                return False
        return True

    if free(row, col, width, height, set()):
        pos[id(src)] = (row, col)
        return None, pos

    occupied: dict[tuple[int, int], Item] = {}
    for item in others:
        for cell in _covered(item, pos[id(item)]):
            occupied[cell] = item
    mobile: list[Item] = []
    seen: set[int] = set()
    for item in others:
        if _overlaps(pos[id(item)], item, row, col, width, height) and id(item) not in seen:
            seen.add(id(item))
            mobile.append(item)
    cursor = row * columns + col
    while cursor < limit * columns:
        cell_row, cell_col = divmod(cursor, columns)
        item = occupied.get((cell_row, cell_col))
        if item is None:
            break
        if id(item) not in seen:
            seen.add(id(item))
            mobile.append(item)
        cursor += 1
    if not mobile:
        return "That spot is taken.", None

    ignore = {id(item) for item in mobile}
    placed = {id(item): pos[id(item)] for item in others if id(item) not in ignore}
    placed[id(src)] = (row, col)

    def open_at(at_row: int, at_col: int, at_w: int, at_h: int) -> bool:
        if at_row < 0 or at_col < 0 or at_col + at_w > columns or at_row + at_h > limit:
            return False
        claim = {(r, c) for r in range(at_row, at_row + at_h) for c in range(at_col, at_col + at_w)}
        for item_id, origin in placed.items():
            if item_id == id(src):
                owner = src
            else:
                owner = next(item for item in others if id(item) == item_id)
            if claim & _covered(owner, origin):
                return False
        return True

    mobile.sort(key=lambda item: pos[id(item)])
    cursor = row * columns + col
    for item in mobile:
        item_w, item_h = span(item)
        found = None
        scan = cursor
        while scan < limit * columns:
            at_row, at_col = divmod(scan, columns)
            if open_at(at_row, at_col, item_w, item_h):
                found = (at_row, at_col)
                break
            scan += 1
        if found is None:
            return "That page is full.", None
        placed[id(item)] = found
        cursor = found[0] * columns + found[1] + 1
    return None, placed


def _apply(page: list[Item], src: Item, updates: dict[int, tuple[int, int]]) -> None:
    kept = [item for item in page if item is not src and id(item) in updates]
    if id(src) in updates:
        kept.append(src)
    for item in kept:
        item[POS_ROW], item[POS_COL] = updates[id(item)]
    kept.sort(key=lambda item: (item[POS_ROW], item[POS_COL], id(item)))
    page[:] = kept


def _end_cell(page: list[Item], src: Item) -> tuple[int, int] | None:
    """First free cell at or after the last icon that stays.

    A page that will be empty starts at the origin. An icon that is already
    alone on the page stays where it is, so this does not pull it to the top.
    """
    columns = active_screen().columns
    rows = active_screen().rows
    positions = _positions_of(page)
    others = [item for item in page if item is not src and not _drops_folder(item, src)]
    width, height = span(src)
    if not others:
        if any(item is src for item in page):
            return positions[id(src)]
        if height > rows or width > columns:
            return None
        return 0, 0
    pos = {id(item): positions[id(item)] for item in others}
    grown = any(pos[id(item)][0] + span(item)[1] > rows for item in others)
    limit = _limit_for(others, pos, 0, 1) if grown else rows
    occupied: set[tuple[int, int]] = set()
    last = 0
    for item in others:
        row, col = pos[id(item)]
        last = max(last, row * columns + col)
        occupied |= _covered(item, (row, col))
    scan = last
    while scan < limit * columns:
        row, col = divmod(scan, columns)
        claim = {(r, c) for r in range(row, row + height) for c in range(col, col + width)}
        if col + width <= columns and row + height <= limit and not (claim & occupied):
            return row, col
        scan += 1
    return None


def _page_spot(page: list[Item], src: Item, index_text: str) -> tuple[int, int] | None | str:
    """Where a page drop wants to land. None means the icon is already there."""
    if index_text.startswith("cell:"):
        _cell, row_text, col_text = index_text.split(":")
        return int(row_text), int(col_text)
    if index_text == "end" or (index_text.isdigit() and int(index_text) >= len(page)):
        found = _end_cell(page, src)
        return "full" if found is None else found
    if not index_text.isdigit():
        raise ValueError(index_text)
    anchor = page[int(index_text)]
    if anchor is src:
        return None
    positions = _positions_of(page)
    return positions[id(anchor)]


def snap_origin(width: int, height: int, left: float, top: float, columns: int, rows: int) -> tuple[int, int]:
    """The cell for an item's top-left corner, from where that corner is held in cell units.

    The nearest cell wins, then the whole footprint is pulled back inside the page,
    so an item held past the right or bottom edge lands against the edge instead of
    being refused. Every drop of a tall or wide item goes through here.
    """
    col = min(max(int(round(left)), 0), max(0, columns - width))
    row = min(max(int(round(top)), 0), max(0, rows - height))
    return row, col


def _page_rows(page: list[Item]) -> int:
    """Rows on screen: the phone's rows, or more when something already sits past them."""
    columns = active_screen().columns
    rows = active_screen().rows
    return _grid_from(page, _positions_of(page), columns, rows)[0]


def footprint_cells(row: int, col: int, width: int, height: int) -> list[list[int]]:
    return [[r, c] for r in range(row, row + height) for c in range(col, col + width)]


def placement(state: State, source: str, target: str) -> dict:
    """What a drop on `target` would do to the moved item, without doing it.

    `move` and the highlight both read this, so the picture and the drop cannot disagree.
    Returns the page, the cell the item's top-left lands on, every cell it covers,
    whether the drop works, and why not. A drop that is not on a page cell (dock,
    folder, grouping) has no footprint.
    """
    none = {"page": -1, "row": 0, "col": 0, "w": 1, "h": 1, "cells": [], "valid": False, "reason": ""}
    try:
        src = _object_at(state, source)
    except (KeyError, IndexError, ValueError):
        return none
    head, _, rest = target.partition(":")
    kind, _, tail = rest.partition(":")
    if head != "at" or kind != "page":
        return none
    try:
        page_text, _, index_text = tail.partition(":")
        page = state[int(page_text) + 1]
        spot = _page_spot(page, src, index_text)
    except (KeyError, IndexError, ValueError):
        return none
    width, height = span(src)
    out = dict(none, page=int(page_text), w=width, h=height)
    if spot is None:
        found = find(state, src)
        spot = _positions_of(page)[id(src)] if found and found[0] == "page" else None
        if spot is None:
            return out
    if spot == "full":
        return dict(out, reason="That page is full.")
    row, col = spot
    error, _updates = _plan(page, src, row, col)
    return dict(out, row=row, col=col, cells=footprint_cells(row, col, width, height), valid=error is None, reason=error or "")


def drop_for(state: State, source: str, page_index: int, left: float, top: float) -> dict:
    """The drop for an item held so that its top-left corner is at (left, top) cells on a page.

    This is how a widget, or any item bigger than one cell, finds its place from where
    the pointer is. It answers with the target to move to and the same footprint as `placement`.
    """
    try:
        src = _object_at(state, source)
        page = state[page_index + 1]
    except (KeyError, IndexError, ValueError):
        return {"target": "", "page": -1, "cells": [], "valid": False, "reason": "", "row": 0, "col": 0, "w": 1, "h": 1}
    width, height = span(src)
    rows = max(_page_rows([item for item in page if item is not src]), active_screen().rows)
    row, col = snap_origin(width, height, left, top, active_screen().columns, rows)
    target = f"at:page:{page_index}:cell:{row}:{col}"
    return dict(placement(state, source, target), target=target)


def strip_positions(state: State) -> None:
    """Drop editor coordinates so a push sends the icon list the phone already speaks."""
    for page in state[1:]:
        for item in page:
            if isinstance(item, dict):
                item.pop(POS_ROW, None)
                item.pop(POS_COL, None)


def gaps_before_send(state: State) -> list[int]:
    """Pages where a Send will move something, as page numbers counted from 1.

    The phone takes a page as a list in order and has no empty cells, so a page changes on Send when an item
    sits past a free cell. A widget covers all of its cells, so those are not free. Space after the last item
    is not a gap. A page with no gap goes to the phone exactly as it is laid out here.
    """
    pages: list[int] = []
    for number, page in enumerate(state[1:], start=1):
        positions = _positions_of(page)
        if not positions:
            continue
        columns = active_screen().columns
        covered: set[int] = set()
        last_origin = -1
        for item in page:
            row, col = positions[id(item)]
            last_origin = max(last_origin, row * columns + col)
            width, height = span(item)
            for r in range(row, row + height):
                for c in range(col, col + width):
                    covered.add(r * columns + c)
        if any(index not in covered for index in range(last_origin)):
            pages.append(number)
    return pages


def has_holes(state: State) -> bool:
    """True when a Send would close a gap on any page."""
    return bool(gaps_before_send(state))


def fingerprint(state: State) -> str:
    """Identity plus page coordinates, so a gap counts as a change."""
    def entry(item: Item, at: tuple[int, int]) -> dict:
        if is_folder(item):
            body: dict = {
                "folder": [ident(icon) for icon in flatten_folder(item)],
                "name": item.get("displayName") or "",
            }
        else:
            body = {"id": ident(item)}
        body["at"] = [at[0], at[1]]
        return body

    pages = []
    for page in state[1:]:
        positions = _positions_of(page)
        pages.append([entry(item, positions[id(item)]) for item in page])
    payload = {"dock": [ident(item) for item in state[0]], "pages": pages}
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def source_for(state: State, obj: Item) -> str:
    loc = find(state, obj)
    if loc is None:
        return ""
    if loc[0] == "dock":
        return f"dock:{loc[1]}"
    if loc[0] == "page":
        return f"page:{loc[1]}:{loc[2]}"
    if loc[0] == "folder":
        return f"folder:{loc[1]}:{loc[2]}:{loc[3]}:{loc[4]}"
    return ""


def pack(items: list[Item], columns: int | None = None, rows: int | None = None):
    """Place items in reading order. Returns placements, grid, and whether it fit."""
    columns = active_screen().columns if columns is None else columns
    rows = active_screen().rows if rows is None else rows
    grid = [[None for _ in range(columns)] for _ in range(rows)]
    placements = []
    cursor = 0

    def free_at(row: int, col: int, width: int, height: int) -> bool:
        if row + height > rows or col + width > columns:
            return False
        return all(grid[r][c] is None for r in range(row, row + height) for c in range(col, col + width))

    for index, item in enumerate(items):
        width, height = span(item)
        found = None
        pos = cursor
        limit = rows * columns
        while pos < limit:
            row, col = divmod(pos, columns)
            if free_at(row, col, width, height):
                found = (row, col)
                break
            pos += 1
        if found is None:
            return None
        row, col = found
        for r in range(row, row + height):
            for c in range(col, col + width):
                grid[r][c] = index
        placements.append({"index": index, "row": row, "col": col, "w": width, "h": height})
        cursor = row * columns + col + 1
    return placements, grid


def page_fits(items: list[Item], columns: int | None = None, rows: int | None = None) -> bool:
    return pack(items, columns, rows) is not None


def _grid_from(items: list[Item], positions: dict[int, tuple[int, int]], columns: int, rows: int):
    """Occupancy grid tall enough for the icons. Overflow means a cell is past the phone grid."""
    row_count = rows
    overflow = False
    for item in items:
        row, col = positions[id(item)]
        width, height = span(item)
        row_count = max(row_count, row + height)
        if row < 0 or col < 0 or col + width > columns or row + height > rows:
            overflow = True
    grid = [[None for _ in range(columns)] for _ in range(max(row_count, 1))]
    for index, item in enumerate(items):
        row, col = positions[id(item)]
        width, height = span(item)
        for r in range(row, row + height):
            for c in range(col, col + width):
                if r < 0 or c < 0 or r >= len(grid) or c >= columns:
                    overflow = True
                    continue
                if grid[r][c] is not None:
                    overflow = True
                grid[r][c] = index
    return max(row_count, rows), overflow, grid


def _after_target(page_index: int, row: int, col: int, width: int, height: int, row_count: int, columns: int) -> str:
    """First cell the tile does not cover. A tile that fills through the grid reports its own origin."""
    covered = {(r, c) for r in range(row, row + height) for c in range(col, col + width)}
    pos = row * columns + col + 1
    while pos < row_count * columns:
        cell_row, cell_col = divmod(pos, columns)
        if (cell_row, cell_col) not in covered:
            return f"at:page:{page_index}:cell:{cell_row}:{cell_col}"
        pos += 1
    return f"at:page:{page_index}:cell:{row}:{col}"


def _tile(item: Item, source: str, place: dict) -> dict:
    preview: list[str] = []
    count = 0
    page_count = 0
    if is_folder(item):
        icons = flatten_folder(item)
        count = len(icons)
        page_count = folder_page_count(item)
        preview = [ident(icon) for icon in icons[:9]]
    names = [label(item)]
    if is_folder(item):
        names.extend(label(icon) for icon in icons)
    return {
        "source": source,
        "ident": ident(item) if not is_folder(item) else "",
        "name": label(item),
        "search": " ".join(names).lower(),
        "kind": kind_of(item),
        "row": place["row"],
        "col": place["col"],
        "w": place["w"],
        "h": place["h"],
        "count": count,
        "pageCount": page_count,
        "preview": preview,
        "letter": _letter(label(item)),
    }


def monogram(name: str) -> str:
    return _letter(name)


def _letter(name: str) -> str:
    parts = [part for part in name.replace("&", " ").split() if part]
    if len(parts) >= 2 and parts[0][:1].isalnum() and parts[1][:1].isalnum():
        return (parts[0][0] + parts[1][0]).upper()
    cleaned = "".join(ch for ch in name if ch.isalnum())
    return (cleaned[:2] or "?").upper()


def _cells(grid, target_for) -> list[dict]:
    cells = []
    rows = len(grid)
    columns = len(grid[0]) if grid else 0
    for row in range(rows):
        for col in range(columns):
            owner = grid[row][col]
            cells.append({
                "row": row,
                "col": col,
                "occupied": owner is not None,
                "target": target_for(owner, row, col),
            })
    return cells


def build_view(state: State, columns: int | None = None, rows: int | None = None) -> dict:
    columns = active_screen().columns if columns is None else columns
    rows = active_screen().rows if rows is None else rows
    current = active_screen()
    dock_count = current.dock
    dock_slots = []
    for slot in range(dock_count):
        if slot < len(state[0]):
            tile = _tile(state[0][slot], f"dock:{slot}", {"row": 0, "col": slot, "w": 1, "h": 1})
            tile["empty"] = False
            tile["target"] = f"at:dock:{slot}"
            tile["onto"] = ""
        else:
            tile = {
                "empty": True,
                "target": "at:dock:end",
                "onto": "",
                "source": "",
                "ident": "",
                "name": "",
                "search": "",
                "letter": "",
                "kind": "app",
            }
        dock_slots.append(tile)

    pages = []
    for page_index, items in enumerate(state[1:]):
        positions = _positions_of(items, columns, rows)
        row_count, overflow, grid = _grid_from(items, positions, columns, rows)
        tiles = []
        for index, item in enumerate(items):
            row, col = positions[id(item)]
            width, height = span(item)
            tile = _tile(item, f"page:{page_index}:{index}", {"row": row, "col": col, "w": width, "h": height})
            tile["insert"] = f"at:page:{page_index}:cell:{row}:{col}"
            tile["after"] = _after_target(page_index, row, col, width, height, row_count, columns)
            if tile["kind"] == "folder":
                tile["onto"] = f"into:{page_index}:{index}"
            elif tile["kind"] in ("app", "shortcut"):
                tile["onto"] = f"onto:{page_index}:{index}"
            else:
                tile["onto"] = ""
            tiles.append(tile)

        def target_for(owner, cell_row, cell_col, page_index=page_index):
            return f"at:page:{page_index}:cell:{cell_row}:{cell_col}"

        cells = _cells(grid, target_for)
        pages.append({
            "index": page_index,
            "overflow": overflow,
            "rows": row_count,
            "tiles": tiles,
            "cells": cells,
            "empty": not items,
        })
    return {
        "columns": columns,
        "rows": rows,
        "dockSlots": dock_count,
        "family": current.family,
        "chassisW": current.chassis_w,
        "chassisH": current.chassis_h,
        "island": current.island,
        "dock": dock_slots,
        "pages": pages,
    }


def folder_payload(state: State, folder: Item) -> dict | None:
    loc = find(state, folder)
    if loc is None or loc[0] != "page" or not is_folder(folder):
        return None
    page_index, index = loc[1], loc[2]
    apps = flatten_folder(folder)
    pages = []
    for start in range(0, max(len(apps), 1), FOLDER_SLOTS):
        chunk = apps[start : start + FOLDER_SLOTS]
        tiles = []
        for offset, icon in enumerate(chunk):
            flat = start + offset
            folder_page, folder_index = divmod(flat, FOLDER_SLOTS)
            # The stored page may differ if an earlier page is short. Trust `find`.
            actual = find(state, icon)
            if actual and actual[0] == "folder":
                folder_page, folder_index = actual[3], actual[4]
                flat = actual[5]
            tiles.append({
                "source": f"folder:{page_index}:{index}:{folder_page}:{folder_index}",
                "ident": ident(icon),
                "name": label(icon),
                "kind": kind_of(icon),
                "letter": _letter(label(icon)),
                "flat": flat,
                "slot": offset,
            })
        cells = []
        for slot in range(FOLDER_SLOTS):
            flat = start + slot
            cells.append({
                "slot": slot,
                "empty": slot >= len(chunk),
                "target": f"at:folder:{page_index}:{index}:{flat if slot < len(chunk) else 'end'}",
            })
        pages.append({"tiles": tiles, "cells": cells})
    if not pages:
        pages = [{"tiles": [], "cells": []}]
    return {
        "source": f"page:{page_index}:{index}",
        "name": label(folder),
        "count": len(apps),
        "pages": pages,
    }


def placement_text(state: State) -> dict[str, str]:
    placed: dict[str, str] = {}
    for index, item in enumerate(state[0]):
        if ident(item):
            placed[ident(item)] = "Dock"
    for page_index, page in enumerate(state[1:], start=1):
        for item in page:
            if is_folder(item):
                where = f"Page {page_index} / {label(item)}"
                for icon in flatten_folder(item):
                    if ident(icon):
                        placed[ident(icon)] = where
            elif ident(item):
                placed[ident(item)] = f"Page {page_index}"
    return placed


def change_summary(before: State, after: State, limit: int = 14) -> list[str]:
    old = placement_text(before)
    new = placement_text(after)
    names = {ident(icon): label(icon) for icon in walk_icons(after)}
    lines = []
    for key, where in new.items():
        if old.get(key) != where:
            lines.append(f"{names.get(key, key)} → {where}")
    lines.sort()
    extra = len(lines) - limit
    if extra > 0:
        return lines[:limit] + [f"{extra} more moves"]
    return lines


def catalog(state: State) -> list[dict]:
    rows = []
    for icon in walk_icons(state):
        key = ident(icon)
        if not key:
            continue
        rows.append({
            "id": key,
            "name": label(icon),
            "kind": kind_of(icon),
            "cells": cells_for(icon),
        })
    rows.sort(key=lambda row: (row["kind"] != "widget", row["name"].casefold()))
    return rows


def current_outline(state: State) -> dict:
    def entry(item: Item):
        if is_folder(item):
            return {"name": label(item), "apps": [ident(icon) for icon in flatten_folder(item)]}
        return ident(item)

    return {
        "dock": [ident(item) for item in state[0]],
        "pages": [[entry(item) for item in page] for page in state[1:]],
    }


def apply_proposal(state: State, proposal: dict) -> tuple[State | None, str | None]:
    """Rebuild pages from a proposal, reusing the original icon dictionaries."""
    if not isinstance(proposal, dict):
        return None, "The model did not return a layout."
    dock_ids = proposal.get("dock")
    pages = proposal.get("pages")
    if not isinstance(dock_ids, list) or not isinstance(pages, list):
        return None, "The layout needs a dock and a list of pages."

    pool: dict[str, Item] = {}
    for icon in walk_icons(state):
        key = ident(icon)
        if not key:
            return None, "An item on the phone has no id, so it can only be moved by hand."
        if key in pool:
            return None, f"{label(icon)} appears twice, so the organizer will not guess."
        pool[key] = icon

    used: list[str] = []

    def take(key: str, *, folder: bool) -> Item:
        if not isinstance(key, str) or key not in pool:
            raise KeyError(key)
        icon = pool.pop(key)
        if folder and is_widget(icon):
            raise ValueError(f"{label(icon)} is a widget and has to stay on a page.")
        used.append(key)
        return icon

    try:
        new_dock = []
        for key in dock_ids:
            icon = take(key, folder=False)
            if is_widget(icon):
                return None, f"{label(icon)} is a widget and cannot sit in the dock."
            new_dock.append(icon)
        dock_cap = active_screen().dock
        if len(new_dock) > dock_cap:
            return None, f"The dock holds {dock_cap} icons."
        new_pages = []
        for page in pages:
            if not isinstance(page, list):
                return None, "Each page has to be a list."
            built = []
            for entry in page:
                if isinstance(entry, str):
                    built.append(take(entry, folder=False))
                    continue
                if not isinstance(entry, dict) or not isinstance(entry.get("apps"), list):
                    return None, "A folder needs a name and a list of apps."
                apps = [take(key, folder=True) for key in entry["apps"]]
                if not apps:
                    return None, "A folder cannot be empty."
                name = " ".join(str(entry.get("name") or "Folder").split())[:80] or "Folder"
                built.append({
                    "listType": "folder",
                    "displayName": name,
                    "iconLists": [apps[start : start + FOLDER_SLOTS] for start in range(0, len(apps), FOLDER_SLOTS)],
                })
            new_pages.append(built)
    except KeyError:
        return None, "The model invented an app id or used one twice."
    except ValueError as exc:
        return None, str(exc)

    if pool:
        names = ", ".join(label(icon) for icon in list(pool.values())[:6])
        return None, f"The model left out {names}."
    for index, page in enumerate(new_pages, start=1):
        if not page_fits(page):
            return None, f"Page {index} does not fit in 24 cells. Widgets cost 4, 8, or 16."
    if not new_pages:
        new_pages = [[]]
    return [new_dock, *new_pages], None


def proposal_from_text(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("The model did not return JSON.")
    return json.loads(cleaned[start : end + 1])
