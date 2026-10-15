import unittest

from hearth.layout import (
    apply_proposal,
    build_view,
    change_summary,
    flatten_folder,
    folder_payload,
    has_holes,
    ident,
    move,
    pack,
    rename_folder,
    strip_positions,
)


def app(bundle, name=None):
    return {
        "bundleIdentifier": bundle,
        "displayIdentifier": bundle,
        "displayName": name or bundle,
    }


def clip(uuid, name):
    return {"displayIdentifier": uuid, "displayName": name, "webClipURL": "https://example.com/stay"}


def widget(bundle, size="small"):
    return {
        "elementType": "widget",
        "bundleIdentifier": bundle,
        "displayIdentifier": bundle,
        "gridSize": size,
    }


class PackTests(unittest.TestCase):
    def test_three_small_widgets_share_two_rows(self):
        items = [widget("a"), widget("b"), widget("c")]
        placements, _grid = pack(items)
        spots = [(place["row"], place["col"]) for place in placements]
        self.assertEqual(spots, [(0, 0), (0, 2), (2, 0)])

    def test_icons_fill_in_order(self):
        placements, _grid = pack([app(str(i)) for i in range(5)])
        self.assertEqual([(p["row"], p["col"]) for p in placements], [(0, 0), (0, 1), (0, 2), (0, 3), (1, 0)])


class MoveTests(unittest.TestCase):
    def test_move_across_pages_keeps_the_same_object(self):
        icon = app("com.example.one", "One")
        state = [[], [icon, app("com.example.two", "Two")], []]
        self.assertIsNone(move(state, "page:0:0", "at:page:1:end"))
        self.assertIs(state[2][0], icon)

    def test_group_two_apps_and_keep_a_shortcut(self):
        shortcut = clip("AAA", "Clip")
        state = [[], [app("com.example.maps", "Maps"), shortcut]]
        self.assertIsNone(move(state, "page:0:1", "onto:0:0"))
        folder = state[1][0]
        self.assertEqual(folder["displayName"], "Folder")
        self.assertIs(flatten_folder(folder)[1], shortcut)
        self.assertEqual(shortcut["webClipURL"], "https://example.com/stay")

    def test_drop_into_folder(self):
        state = [[], [
            {"listType": "folder", "displayName": "Tools", "iconLists": [[app("a", "A")]]},
            app("b", "B"),
        ]]
        self.assertIsNone(move(state, "page:0:1", "into:0:0"))
        self.assertEqual([ident(icon) for icon in flatten_folder(state[1][0])], ["a", "b"])

    def test_widget_does_not_enter_a_folder(self):
        state = [[], [
            {"listType": "folder", "displayName": "Tools", "iconLists": [[app("a", "A")]]},
            widget("sample.widget"),
        ]]
        self.assertIsNotNone(move(state, "page:0:1", "into:0:0"))
        self.assertTrue(state[1][1].get("elementType") == "widget")

    def test_full_dock_pushes_the_last_icon_to_page_one(self):
        dock = [app(f"d{i}", f"D{i}") for i in range(4)]
        extra = app("extra", "Extra")
        state = [dock, [extra]]
        self.assertIsNone(move(state, "page:0:0", "at:dock:0"))
        self.assertEqual(len(state[0]), 4)
        self.assertIs(state[0][0], extra)
        self.assertEqual(ident(state[1][0]), "d3")

    def test_rename(self):
        state = [[], [{"listType": "folder", "displayName": "Photos", "iconLists": [[app("a", "A")]]}]]
        self.assertIsNone(rename_folder(state, "page:0:0", "Albums"))
        self.assertEqual(state[1][0]["displayName"], "Albums")

    def test_dragging_onto_itself_does_nothing(self):
        icon = app("a", "A")
        state = [[], [icon, app("b", "B")]]
        self.assertIsNone(move(state, "page:0:0", "at:page:0:0"))
        self.assertIs(state[1][0], icon)

    def test_place_an_icon_between_folders(self):
        first = {"listType": "folder", "displayName": "One", "iconLists": [[app("a", "A")]]}
        second = {"listType": "folder", "displayName": "Two", "iconLists": [[app("b", "B")]]}
        loose = app("c", "C")
        state = [[], [first, second, loose]]
        self.assertIsNone(move(state, "page:0:2", "at:page:0:1"))
        self.assertIs(state[1][0], first)
        self.assertIs(state[1][1], loose)
        self.assertIs(state[1][2], second)

    def test_move_an_icon_out_of_a_folder(self):
        icon = app("a", "A")
        stay = app("b", "B")
        neighbor = app("c", "C")
        state = [[], [
            {"listType": "folder", "displayName": "Tools", "iconLists": [[icon, stay]]},
            neighbor,
        ]]
        self.assertIsNone(move(state, "folder:0:0:0:0", "at:page:0:1"))
        self.assertEqual([ident(item) for item in flatten_folder(state[1][0])], ["b"])
        self.assertIs(state[1][1], icon)
        self.assertIs(state[1][2], neighbor)

    def test_the_last_icon_leaves_and_the_folder_goes(self):
        icon = app("a", "A")
        neighbor = app("c", "C")
        state = [[], [
            {"listType": "folder", "displayName": "Tools", "iconLists": [[icon]]},
            neighbor,
        ]]
        self.assertIsNone(move(state, "folder:0:0:0:0", "at:page:0:end"))
        self.assertEqual([ident(item) for item in state[1]], ["c", "a"])

    def test_reordering_a_folders_only_icon_keeps_it(self):
        icon = app("a", "A")
        state = [[], [{"listType": "folder", "displayName": "Tools", "iconLists": [[icon]]}]]
        self.assertIsNone(move(state, "folder:0:0:0:0", "at:folder:0:0:end"))
        self.assertEqual(state[1][0]["displayName"], "Tools")
        self.assertIs(flatten_folder(state[1][0])[0], icon)

    def test_reorder_inside_a_folder(self):
        first = app("a", "A")
        second = app("b", "B")
        state = [[], [{"listType": "folder", "displayName": "Tools", "iconLists": [[first, second]]}]]
        self.assertIsNone(move(state, "folder:0:0:0:0", "at:folder:0:0:end"))
        self.assertEqual([ident(item) for item in flatten_folder(state[1][0])], ["b", "a"])

    def test_move_from_folder_into_the_dock(self):
        icon = app("a", "A")
        state = [[app("d", "D")], [
            {"listType": "folder", "displayName": "Tools", "iconLists": [[icon, app("b", "B")]]},
        ]]
        self.assertIsNone(move(state, "folder:0:0:0:0", "at:dock:1"))
        self.assertIs(state[0][1], icon)
        self.assertEqual([ident(item) for item in flatten_folder(state[1][0])], ["b"])

    def test_neighbor_targets_are_insert_before(self):
        folder = {"listType": "folder", "displayName": "Tools", "iconLists": [[app("a", "A")]]}
        view = build_view([[app("d", "D"), app("e", "E")], [folder, app("b", "B")]])
        tiles = view["pages"][0]["tiles"]
        self.assertEqual(tiles[0]["insert"], "at:page:0:cell:0:0")
        self.assertEqual(tiles[0]["after"], "at:page:0:cell:0:1")
        self.assertEqual(tiles[0]["onto"], "into:0:0")
        self.assertEqual(tiles[1]["insert"], "at:page:0:cell:0:1")
        self.assertEqual(tiles[1]["after"], "at:page:0:cell:0:2")
        self.assertEqual(tiles[1]["onto"], "onto:0:1")
        self.assertEqual(view["pages"][0]["cells"][2]["target"], "at:page:0:cell:0:2")
        self.assertEqual(view["dock"][0]["target"], "at:dock:0")
        self.assertEqual(view["dock"][2]["target"], "at:dock:end")

    def test_folder_page_count_is_two_only_when_a_second_page_has_icons(self):
        icons = [app(f"com.example.app{i}", f"App {i}") for i in range(10)]
        many = {
            "listType": "folder",
            "displayName": "Tools",
            "iconLists": [icons[:9], icons[9:]],
        }
        view = build_view([[], [many]])
        tile = view["pages"][0]["tiles"][0]
        self.assertEqual(tile["kind"], "folder")
        self.assertEqual(tile["pageCount"], 2)
        self.assertEqual(tile["count"], 10)

        one = {"listType": "folder", "displayName": "One", "iconLists": [icons[:3], []]}
        view = build_view([[], [one, app("com.example.solo", "Solo")]])
        self.assertEqual(view["pages"][0]["tiles"][0]["pageCount"], 1)
        self.assertEqual(view["pages"][0]["tiles"][1]["pageCount"], 0)

        docked = {
            "listType": "folder",
            "displayName": "Docked",
            "iconLists": [icons[:9], icons[9:]],
        }
        view = build_view([[docked], []])
        self.assertEqual(view["dock"][0]["pageCount"], 2)

    def test_drop_on_an_empty_cell_leaves_the_gap(self):
        first = app("a", "A")
        second = app("b", "B")
        state = [[], [first, second]]
        self.assertIsNone(move(state, "page:0:1", "at:page:0:cell:0:3"))
        view = build_view(state)
        spots = [(tile["row"], tile["col"], tile["ident"]) for tile in view["pages"][0]["tiles"]]
        self.assertEqual(spots, [(0, 0, "a"), (0, 3, "b")])
        self.assertTrue(has_holes(state))
        self.assertIsNone(move(state, "page:0:0", "at:page:0:cell:2:0"))
        view = build_view(state)
        spots = [(tile["row"], tile["col"], tile["ident"]) for tile in view["pages"][0]["tiles"]]
        self.assertEqual(spots, [(0, 3, "b"), (2, 0, "a")])

    def test_a_widget_keeps_its_span_beside_a_gap(self):
        sample = widget("sample.widget")
        icon = app("a", "A")
        state = [[], [sample, icon]]
        self.assertIsNone(move(state, "page:0:1", "at:page:0:cell:3:0"))
        view = build_view(state)
        widget_tile = view["pages"][0]["tiles"][0]
        icon_tile = view["pages"][0]["tiles"][1]
        self.assertEqual((widget_tile["row"], widget_tile["col"], widget_tile["w"], widget_tile["h"]), (0, 0, 2, 2))
        self.assertEqual((icon_tile["row"], icon_tile["col"]), (3, 0))

    def test_a_later_icon_stays_when_a_hole_absorbs_the_shift(self):
        first = app("a", "A")
        second = app("b", "B")
        third = app("c", "C")
        incoming = app("d", "D")
        state = [[incoming], [first, second, third]]
        self.assertIsNone(move(state, "page:0:2", "at:page:0:cell:0:3"))
        self.assertIsNone(move(state, "dock:0", "at:page:0:cell:0:0"))
        view = build_view(state)
        spots = [(tile["col"], tile["ident"]) for tile in view["pages"][0]["tiles"] if tile["row"] == 0]
        self.assertEqual(spots, [(0, "d"), (1, "a"), (2, "b"), (3, "c")])

    def test_a_folder_stays_packed(self):
        first = app("a", "A")
        second = app("b", "B")
        state = [[], [{"listType": "folder", "displayName": "Tools", "iconLists": [[first, second]]}]]
        self.assertIsNone(move(state, "folder:0:0:0:0", "at:folder:0:0:end"))
        payload = folder_payload(state, state[1][0])
        filled = [cell["empty"] for cell in payload["pages"][0]["cells"]]
        self.assertEqual(filled[:2], [False, False])
        self.assertTrue(all(filled[2:]))
        self.assertEqual([ident(icon) for icon in flatten_folder(state[1][0])], ["b", "a"])

    def test_positions_are_not_part_of_the_pushed_list(self):
        first = app("a", "A")
        second = app("b", "B")
        state = [[], [first, second]]
        self.assertIsNone(move(state, "page:0:1", "at:page:0:cell:0:3"))
        self.assertIn("_col", second)
        strip_positions(state)
        self.assertNotIn("_col", second)
        self.assertNotIn("_row", first)

    def test_an_icon_cannot_land_past_the_grid(self):
        state = [[], [app("a", "A"), widget("sample.widget")]]
        self.assertIsNotNone(move(state, "page:0:0", "at:page:0:cell:0:4"))
        self.assertIsNotNone(move(state, "page:0:1", "at:page:0:cell:0:3"))

    def test_the_last_cell_does_not_close_a_hole(self):
        first = app("a", "A")
        last = app("b", "B")
        state = [[], [first, last]]
        self.assertIsNone(move(state, "page:0:1", "at:page:0:cell:5:3"))
        view = build_view(state)
        tile = next(tile for tile in view["pages"][0]["tiles"] if tile["ident"] == "b")
        self.assertEqual((tile["row"], tile["col"]), (5, 3))
        self.assertEqual(tile["after"], tile["insert"])
        self.assertEqual(tile["insert"], "at:page:0:cell:5:3")
        self.assertIsNone(move(state, "page:0:1", tile["after"]))
        view = build_view(state)
        spots = [(tile["row"], tile["col"], tile["ident"]) for tile in view["pages"][0]["tiles"]]
        self.assertEqual(spots, [(0, 0, "a"), (5, 3, "b")])

    def test_a_lone_icon_sent_to_the_end_stays_where_it_is(self):
        icon = app("a", "A")
        state = [[], [icon]]
        self.assertIsNone(move(state, "page:0:0", "at:page:0:cell:2:1"))
        self.assertIsNone(move(state, "page:0:0", "at:page:0:end"))
        view = build_view(state)
        tile = view["pages"][0]["tiles"][0]
        self.assertEqual((tile["row"], tile["col"]), (2, 1))
        self.assertTrue(has_holes(state))

    def test_moving_an_icon_to_the_dock_leaves_its_cell_empty(self):
        first = app("a", "A")
        middle = app("b", "B")
        last = app("c", "C")
        state = [[], [first, middle, last]]
        self.assertIsNone(move(state, "page:0:2", "at:page:0:cell:0:3"))
        self.assertIsNone(move(state, "page:0:1", "at:dock:0"))
        self.assertIs(state[0][0], middle)
        view = build_view(state)
        spots = [(tile["row"], tile["col"], tile["ident"]) for tile in view["pages"][0]["tiles"]]
        self.assertEqual(spots, [(0, 0, "a"), (0, 3, "c")])
        self.assertTrue(has_holes(state))


class ProposalTests(unittest.TestCase):
    def test_apply_reuses_widgets_and_shortcuts(self):
        shortcut = clip("CLIP", "Clip")
        sample = widget("sample.widget")
        maps = app("maps", "Maps")
        phone = app("phone", "Phone")
        state = [[phone], [maps, shortcut, sample]]
        proposal = {
            "summary": "One folder, then the widget.",
            "dock": ["phone"],
            "pages": [[{"name": "Travel", "apps": ["maps", "CLIP"]}], ["sample.widget"]],
        }
        rebuilt, error = apply_proposal(state, proposal)
        self.assertIsNone(error)
        self.assertIs(rebuilt[0][0], phone)
        self.assertIs(flatten_folder(rebuilt[1][0])[1], shortcut)
        self.assertIs(rebuilt[2][0], sample)
        self.assertTrue(change_summary(state, rebuilt))

    def test_reject_a_missing_app(self):
        state = [[], [app("a", "A"), app("b", "B")]]
        rebuilt, error = apply_proposal(state, {"dock": [], "pages": [["a"]]})
        self.assertIsNone(rebuilt)
        self.assertIn("left out", error)

    def test_reject_a_widget_in_a_folder(self):
        state = [[], [widget("sample.widget"), app("a", "A")]]
        rebuilt, error = apply_proposal(state, {
            "dock": [],
            "pages": [[{"name": "Home", "apps": ["sample.widget", "a"]}]],
        })
        self.assertIsNone(rebuilt)
        self.assertIn("widget", error)

    def test_view_marks_a_shortcut(self):
        view = build_view([[], [clip("AAA", "Clip")]])
        self.assertEqual(view["pages"][0]["tiles"][0]["kind"], "shortcut")

    def test_dock_slots_are_flat_and_folders_are_searchable(self):
        folder = {
            "listType": "folder",
            "displayName": "Notes",
            "iconLists": [[app("com.example.reminders", "Reminders")]],
        }
        view = build_view([[app("com.apple.mobilephone", "Phone")], [folder]])
        slot = view["dock"][0]
        self.assertEqual(slot["ident"], "com.apple.mobilephone")
        self.assertEqual(slot["source"], "dock:0")
        self.assertNotIn("tile", slot)
        self.assertFalse(slot["empty"])
        self.assertTrue(view["dock"][3]["empty"])
        self.assertEqual(view["dock"][3]["target"], "at:dock:end")
        blob = view["pages"][0]["tiles"][0]["search"]
        self.assertIn("notes", blob)
        self.assertIn("reminders", blob)


class OpenFolderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from PySide6.QtGui import QGuiApplication

        cls._app = QGuiApplication.instance() or QGuiApplication([])
        cls._versions = tempfile.TemporaryDirectory()
        cls._version_patch = patch(
            "hearth.device.version_dir",
            return_value=Path(cls._versions.name),
        )
        cls._version_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls._version_patch.stop()
        cls._versions.cleanup()

    def test_the_open_folder_closes_when_its_last_icon_leaves(self):
        from hearth.controller import Controller

        controller = Controller()
        icon = app("a", "A")
        controller._state = [[], [
            {"listType": "folder", "displayName": "Tools", "iconLists": [[icon]]},
            app("b", "B"),
        ]]
        controller.openFolder("page:0:0")
        self.assertEqual(controller.folder["name"], "Tools")
        controller.move("folder:0:0:0:0", "at:page:0:end")
        self.assertEqual(controller.folder, {})
        self.assertEqual([ident(item) for item in controller._state[1]], ["b", "a"])

    def test_the_folder_stays_open_while_it_still_has_icons(self):
        from hearth.controller import Controller

        controller = Controller()
        icon = app("a", "A")
        controller._state = [[], [
            {"listType": "folder", "displayName": "Tools", "iconLists": [[icon]]},
            app("b", "B"),
        ]]
        controller.openFolder("page:0:0")
        controller.move("page:0:1", "into:0:0")
        self.assertEqual(controller.folder["name"], "Tools")
        self.assertEqual(controller.folder["count"], 2)


if __name__ == "__main__":
    unittest.main()
