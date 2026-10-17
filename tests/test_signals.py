"""Cheap popularity hints for the organizer: where an app sits now, and a few facts the phone lists."""

import asyncio
import json
import plistlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QGuiApplication

from hearth import ai, device, drivers, facts, layout
from hearth.controller import Controller
from tests.test_no_default_model import Home, wait_for


def app(name):
    return {"bundleIdentifier": name, "displayIdentifier": name, "displayName": name}


def widget(name):
    return {"elementType": "widget", "bundleIdentifier": name, "displayIdentifier": name, "gridSize": "small"}


def folder(name, *pages):
    return {"listType": "folder", "displayName": name, "iconLists": [list(page) for page in pages]}


STATE = [
    [app("dock.phone"), app("dock.safari")],
    [app("p1.a"), widget("p1.widget"), app("p1.c"), folder("Games", [app("g.one"), app("g.two")], [app("g.three")])],
    [app("p2.a")],
]


class WhereTests(unittest.TestCase):
    def test_dock_apps_say_their_slot(self):
        where = layout.where_now(STATE)
        self.assertEqual(where["dock.phone"], "dock 1")
        self.assertEqual(where["dock.safari"], "dock 2")

    def test_page_items_say_page_and_place(self):
        where = layout.where_now(STATE)
        self.assertEqual(where["p1.a"], "page 1, item 1")
        self.assertEqual(where["p1.widget"], "page 1, item 2")
        self.assertEqual(where["p1.c"], "page 1, item 3")
        self.assertEqual(where["p2.a"], "page 2, item 1")

    def test_folder_apps_say_the_folder_and_its_page(self):
        where = layout.where_now(STATE)
        self.assertEqual(where["g.one"], 'folder "Games" on page 1, item 1')
        self.assertEqual(where["g.three"], 'folder "Games" on page 1, item 3')

    def test_every_id_in_the_catalog_has_a_place(self):
        ids = {row["id"] for row in layout.catalog(STATE)}
        self.assertEqual(ids, set(layout.where_now(STATE)))

    def test_an_empty_or_odd_state_does_not_raise(self):
        self.assertEqual(layout.where_now([]), {})
        self.assertEqual(layout.where_now([[], [None, "x"]]), {})


class CatalogTests(unittest.TestCase):
    def test_rows_carry_where_and_no_other_new_key_without_facts(self):
        row = next(r for r in layout.catalog(STATE) if r["id"] == "p1.a")
        self.assertEqual(set(row), {"id", "name", "kind", "cells", "where"})

    def test_facts_are_added_only_for_ids_that_have_them(self):
        known = {"p1.a": {"data_mb": 40, "app_mb": 12, "owned_since": "2021-03"}}
        rows = {r["id"]: r for r in layout.catalog(STATE, known)}
        self.assertEqual(rows["p1.a"]["data_mb"], 40)
        self.assertEqual(rows["p1.a"]["owned_since"], "2021-03")
        self.assertNotIn("data_mb", rows["p1.c"])

    def test_nothing_else_from_facts_leaks_into_the_catalog(self):
        known = {"p1.a": {"data_mb": 1, "app_mb": 2, "owned_since": "2020-01", "secret": "x"}}
        row = next(r for r in layout.catalog(STATE, known) if r["id"] == "p1.a")
        self.assertNotIn("secret", row)


def rows(**extra):
    meta = plistlib.dumps({"com.apple.iTunesStore.downloadInfo": {
        "purchaseDate": "2021-03-14T10:11:12Z",
        "accountInfo": {"AppleID": "someone@example.com", "DSPersonID": 123},
    }, "itemName": "Example"})
    base = {
        "CFBundleIdentifier": "com.example.one",
        "StaticDiskUsage": 12 * 2**20 + 5,
        "DynamicDiskUsage": 40 * 2**20,
        "iTunesMetadata": meta,
    }
    base.update(extra)
    return [base]


class FactsTests(unittest.TestCase):
    def test_sizes_become_whole_megabytes_and_the_date_becomes_a_month(self):
        got = facts.summarize(rows())
        self.assertEqual(got, {"com.example.one": {"app_mb": 12, "data_mb": 40, "owned_since": "2021-03"}})

    def test_the_apple_id_never_survives(self):
        text = json.dumps(facts.summarize(rows()))
        self.assertNotIn("someone", text)
        self.assertNotIn("123", text)
        self.assertNotIn("Example", text)

    def test_a_missing_or_broken_record_still_gives_the_sizes(self):
        got = facts.summarize(rows(iTunesMetadata=b"not a plist"))
        self.assertEqual(got["com.example.one"], {"app_mb": 12, "data_mb": 40})
        got = facts.summarize(rows(iTunesMetadata=None))
        self.assertEqual(got["com.example.one"], {"app_mb": 12, "data_mb": 40})

    def test_rows_without_an_id_or_with_junk_are_skipped(self):
        self.assertEqual(facts.summarize([{}, {"CFBundleIdentifier": ""}, "x", None]), {})
        self.assertEqual(facts.summarize(None), {})
        self.assertEqual(facts.summarize("nope"), {})

    def test_zero_or_odd_sizes_are_left_out(self):
        got = facts.summarize(rows(StaticDiskUsage=0, DynamicDiskUsage="many", iTunesMetadata=None))
        self.assertEqual(got, {})

    def test_the_list_is_capped(self):
        many = [{"CFBundleIdentifier": f"a.b{n}", "DynamicDiskUsage": 2**20} for n in range(facts.LIMIT + 50)]
        self.assertEqual(len(facts.summarize(many)), facts.LIMIT)

    def test_a_date_that_is_not_a_date_is_ignored(self):
        meta = plistlib.dumps({"com.apple.iTunesStore.downloadInfo": {"purchaseDate": "soon"}})
        self.assertEqual(facts.summarize(rows(iTunesMetadata=meta, StaticDiskUsage=0, DynamicDiskUsage=0)), {})


class PromptTests(unittest.TestCase):
    def test_the_prompt_treats_place_as_a_popularity_hint(self):
        text = ai._system()
        self.assertIn("popularity", text)
        self.assertIn("dock first, then page 1", text)
        self.assertIn('"where"', text)

    def test_organize_sends_where_and_facts_to_the_model(self):
        sent = {}

        def fake_chat(base_url, key, body, *rest):
            sent["body"] = body
            return {"choices": [{"message": {"content": json.dumps({"summary": "s", "dock": [], "pages": []})}}]}

        known = {"p1.a": {"data_mb": 77, "app_mb": 5, "owned_since": "2019-02"}}
        with patch.object(ai, "_chat", fake_chat), patch.object(ai, "proposal_from_text", lambda text: {}):
            ai.organize("http://x", "k", "m", "Sort it.", STATE, facts=known)
        user = sent["body"]["messages"][1]["content"]
        self.assertIn('"where": "page 1, item 1"', user)
        self.assertIn('"data_mb": 77', user)
        self.assertIn('"owned_since": "2019-02"', user)

    def test_organize_works_with_no_facts(self):
        sent = {}

        def fake_chat(base_url, key, body, *rest):
            sent["body"] = body
            return {"choices": [{"message": {"content": "{}"}}]}

        with patch.object(ai, "_chat", fake_chat), patch.object(ai, "proposal_from_text", lambda text: {}):
            ai.organize("http://x", "k", "m", "Sort it.", STATE)
        self.assertNotIn("data_mb", sent["body"]["messages"][1]["content"])


class FakeProxy:
    rows: object = []
    seen: dict = {}

    def __init__(self, client):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def browse(self, options=None, attributes=None):
        FakeProxy.seen = {"options": options, "attributes": attributes}
        if isinstance(FakeProxy.rows, Exception):
            raise FakeProxy.rows
        return FakeProxy.rows


class ReadTests(unittest.TestCase):
    def read(self, rows):
        FakeProxy.rows = rows
        module = types.ModuleType("pymobiledevice3.services.installation_proxy")
        module.InstallationProxyService = FakeProxy
        with patch.dict(sys.modules, {"pymobiledevice3.services.installation_proxy": module}):
            return asyncio.run(device._app_facts(object()))

    def test_it_asks_only_for_user_apps_and_four_fields(self):
        self.read([])
        self.assertEqual(FakeProxy.seen["options"], {"ApplicationType": "User"})
        self.assertEqual(
            sorted(FakeProxy.seen["attributes"]),
            ["CFBundleIdentifier", "DynamicDiskUsage", "StaticDiskUsage", "iTunesMetadata"],
        )

    def test_it_returns_the_cut_down_facts(self):
        got = self.read(rows())
        self.assertEqual(got["com.example.one"]["owned_since"], "2021-03")

    def test_any_failure_is_no_facts_and_no_error(self):
        self.assertEqual(self.read(RuntimeError("phone said no")), {})
        self.assertEqual(self.read(None), {})


class WiringTests(Home):
    @classmethod
    def setUpClass(cls):
        cls._app = QGuiApplication.instance() or QGuiApplication([])
        cls._versions = tempfile.TemporaryDirectory()
        cls._patch = patch("hearth.device.version_dir", return_value=Path(cls._versions.name))
        cls._patch.start()

    @classmethod
    def tearDownClass(cls):
        cls._patch.stop()
        cls._versions.cleanup()

    def make(self):
        with patch.object(drivers, "live_probe", return_value=drivers.Probe(system="Linux", socket_open=True)):
            controller = Controller()
        self.addCleanup(controller.shutdown)
        return controller

    def test_facts_from_a_read_reach_the_model_call_and_nothing_else_does(self):
        from hearth import settings
        settings.save("https://api.openai.com/v1", "m", "sk-test", provider="openai")
        controller = self.make()
        controller.chooseModel("m")
        known = {"p1.a": {"data_mb": 9, "owned_since": "2020-05"}}
        with patch.object(device, "save_version", return_value=Path("x")):
            controller._on_pulled({"state": STATE, "name": "Phone", "product": "iPhone1,1", "deviceClass": "iPhone",
                                   "facts": known})
        seen = []

        def organize(*args, **kwargs):
            seen.append(kwargs.get("facts"))
            return {"summary": "ok", "pages": []}

        with patch.object(ai, "organize", side_effect=organize):
            controller.propose("sort")
            wait_for(self, lambda: seen and not controller.busy, "organize")
        self.assertEqual(seen, [known])

    def test_a_read_without_facts_gives_an_empty_set(self):
        controller = self.make()
        with patch.object(device, "save_version", return_value=Path("x")):
            controller._on_pulled({"state": STATE, "name": "Phone", "product": "iPhone1,1", "deviceClass": "iPhone"})
        self.assertEqual(controller._facts, {})


if __name__ == "__main__":
    unittest.main()
